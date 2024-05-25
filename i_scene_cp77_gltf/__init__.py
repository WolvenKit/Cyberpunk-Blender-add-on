def install_dependency(dependency_name):
    print(f"required package: {dependency_name} not found")
    from pip import _internal as pip
    print(f"Attempting to install {dependency_name}")
    try:
        pip.main(['install', dependency_name])
        print(f"Successfully installed {dependency_name}")
    except Exception as e:
        print(f"Failed to install {dependency_name}: {e}")

print('-------------------- Cyberpunk IO Suite Starting--------------------')
print()

import bpy
import bpy.utils.previews
import os
import textwrap
try:
    import PIL
except (ImportError, ModuleNotFoundError):
    install_dependency('pillow')


from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty)
from bpy.types import (Scene, Operator, PropertyGroup, Object, OperatorFileListElement, Panel, AddonPreferences, TOPBAR_MT_file_import, TOPBAR_MT_file_export)
from bpy_extras.io_utils import ImportHelper
from .importers.entity_import import *
from .importers.sector_import import *
from .importers.import_with_materials import *
from bpy_extras.io_utils import ExportHelper
from .exporters.glb_export import *
from .exporters.sectors_export import *
from .exporters.hp_export import *
from .exporters.collision_export import *
from .exporters.mlsetup_export import *
from .main.collisions import *
from .main.animtools import *
from .main.meshtools import *
from .main.bartmoss_functions import *
from .main.script_manager import *
from .main.physmat_lib import physmat_list
from .importers.phys_import import *

bl_info = {
    "name": "Cyberpunk 2077 IO Suite",
    "author": "HitmanHimself, Turk, Jato, dragonzkiller, kwekmaster, glitchered, Simarilius, Doctor Presto, shotlastc, Rudolph2109, Holopointz",
    "version": (1, 5, 5, 3),
    "blender": (4, 0, 0),
    "location": "File > Import-Export",
    "description": "Import and Export WolvenKit Cyberpunk2077 gLTF models with materials, Import .streamingsector and .ent from .json",
    "warning": "",
    "category": "Import-Export",
    "doc_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on#readme",
    "tracker_url": "https://github.com/WolvenKit/Cyberpunk-Blender-add-on/issues/new/choose",
}
plugin_version = ".".join(map(str, bl_info["version"]))
blender_version = ".".join(map(str, bpy.app.version))

icons_dir = os.path.join(os.path.dirname(__file__), "icons")
custom_icon_col = {}
script_dir = get_script_dir()

print()
print(f"Blender Version:{blender_version}")
print(f"Cyberpunk IO Suite version: {plugin_version}")
print()
print('-------------------- Cyberpunk IO Suite Finished--------------------')

class CP77IOSuitePreferences(AddonPreferences):
    bl_idname = __name__

    experimental_features: BoolProperty(
    name= "Enable Experimental Features",
    description="Experimental Features for Mod Developers, may encounter bugs",
    default=False,
    )

    # Define the depotfolder path property
    depotfolder_path: bpy.props.StringProperty(
        name="MaterialDepot Path",
        description="Path to the material depot folder",
        subtype='DIR_PATH',
        default="//MaterialDepot"
    )


# toggle the mod tools tab and its sub panels - default True
    show_modtools: BoolProperty(
    name= "Show Mod Tools",
    description="Show the Mod tools Tab in the 3d viewport",
    default=True,
    )

# only display the panels based on context
    context_only: BoolProperty(
    name= "Only Show Mod Tools in Context",
    description="Show the Mod tools Tab in the 3d viewport",
    default=False,
    )

    show_meshtools: BoolProperty(
    name= "Show the Mesh Tools Panel",
    description="Show the mesh tools panel",
    default=True,
    )

    show_collisiontools: BoolProperty(
    name= "Show the Collision Tools Panel",
    description="Show the Collision tools panel",
    default=True,
    )

    show_animtools: BoolProperty(
    name= "Show the Animation Tools Panel",
    description="Show the anim tools panel",
    default=True,
    )

    show_modtools: BoolProperty(
    name= "Show Mod Tools",
    description="Show the Mod tools Tab in the 3d viewport",
    default=True,
    )

    def draw(self, context):
        layout = self.layout
        box = layout.box()

        row = box.row()
        row.prop(self, "show_modtools",toggle=1)
        row.prop(self, "experimental_features",toggle=1)
        if self.experimental_features:
            row = box.row()
            row.prop(self, "depotfolder_path")
            row = box.row()
        if self.show_modtools:
            row.alignment = 'LEFT'
            box = layout.box()
            box.label(text="Mod Tools Properties")
            split = row.split(factor=0.5,align=True)
            col = split.column(align=True)
            row.alignment = 'LEFT'
            row = box.row()
            col = row.column(align=True)
            col.prop(self, "context_only")
            col.prop(self, "show_meshtools")
            col.prop(self, "show_collisiontools")
            col.prop(self, "show_animtools")


class CP77ScriptManager(Panel):
    bl_label = "Script Manager"
    bl_idname = "CP77_PT_ScriptManagerPanel"
    bl_space_type = 'TEXT_EDITOR'
    bl_region_type = 'UI'
    bl_category = "CP77 Modding"

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()
        # List available scripts
        script_files = [f for f in os.listdir(script_dir) if f.endswith(".py")]

        for script_file in script_files:
            row = col.row(align=True)
            row.operator("script_manager.save_script", text="", icon="APPEND_BLEND").script_file = script_file
            row.operator("script_manager.load_script", text=script_file).script_file = script_file
            row.operator("script_manager.delete_script", text="", icon="X").script_file = script_file

        row = box.row(align=True)
        row.operator("script_manager.create_script")


class CP77CreateScript(Operator):
    bl_idname = "script_manager.create_script"
    bl_label = "Create New Script"
    bl_description = "create a new script in the cp77 modding scripts directory"

    def execute(self, context):
        base_name = "new_script"
        script_name = base_name + ".py"

        # Check if a script with the default name already exists
        i = 1
        while os.path.exists(os.path.join(script_dir, script_name)):
            script_name = f"{base_name}_{i}.py"
            i += 1

        script_path = os.path.join(script_dir, script_name)

        with open(script_path, 'w') as f:
            f.write("# New Script")

        return {'FINISHED'}


class CP77LoadScript(Operator):
    bl_idname = "script_manager.load_script"
    bl_label = "Load Script"
    bl_description = "Click to load or switch to this script, ctrl+click to rename"

    script_file: StringProperty()
    new_name: StringProperty(name="New name", default=".py")

    def execute(self, context):
        script_name = self.script_file

        if self.new_name:
            # Rename the script
            script_path = os.path.join(script_dir, script_file)
            new_script_path = os.path.join(s, self.new_name)

            if os.path.exists(script_path):
                if not os.path.exists(new_script_path):
                    os.rename(script_path, new_script_path)
                    self.report({'INFO'}, f"Renamed '{script_name}' to '{self.new_name}'")
                else:
                    self.report({'ERROR'}, f"A script with the name '{self.new_name}' already exists.")
        else:
            # Check if the script is already loaded
            script_text = bpy.data.texts.get(script_name)
            # Switch to the loaded script if present
            if script_text is not None:
                context.space_data.text = script_text
            else:
                # If the script is not loaded, load it
                script_path = os.path.join(script_dir, script_name)

                if os.path.exists(script_path):
                    with open(script_path, 'r') as f:
                        text_data = bpy.data.texts.new(name=script_name)
                        text_data.from_string(f.read())
                        # Set the loaded script as active
                        context.space_data.text = text_data

        return {'FINISHED'}

    def invoke(self, context, event):
        if event.ctrl:
            # Ctrl+Click to rename
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "new_name")


class CP77SaveScript(Operator):
    bl_idname = "script_manager.save_script"
    bl_label = "Save Script"
    bl_description = "Press to save this script"

    script_file: StringProperty()

    def execute(self, context):
        script_text = context.space_data.text
        if script_text:
            script_path = os.path.join(script_dir, self.script_file)
            with open(script_path, 'w') as f:
                f.write(script_text.as_string())

        return {'FINISHED'}


class CP77DeleteScript(Operator):
    bl_idname = "script_manager.delete_script"
    bl_label = "Delete Script"
    bl_description = "Press to delete this script"

    script_file: StringProperty()

    def execute(self, context):
        script_path = os.path.join(script_dir, self.script_file)

        if os.path.exists(script_path):
            os.remove(script_path)

        return {'FINISHED'}


def SetCyclesRenderer(use_cycles=True, set_gi_params=False):
    # set the render engine for all scenes to Cycles

    if use_cycles:
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

physmats_data = physmat_list()
enum_items = [(mat.get("Name", ""), mat.get("Name", ""), "") for mat in physmats_data]
class CP77_PT_PanelProps(PropertyGroup):
# collision panel props:
    collision_type: EnumProperty(
        name="Collision Type",
        items=[
        ('VEHICLE', "Vehicle", "Generate .phys formatted collisions for a vehicle mod"),
        ('ENTITY', "entColliderComponent", "Generate entCollisionComponents"),
        ('WORLD', "worldCollisionNode", "Generate worldCollisionNode")
        ],
        default='VEHICLE'
    )

    physics_material: EnumProperty(
        items= enum_items,
        name="Physics Material",
        description="Select the physics material for the object"
    )

    collision_shape: EnumProperty(
        name="Collision Shape",
        items=[
        ('CONVEX', "Convex Collider", "Generate a Convex Collider"),
        ('BOX', "Box Collider", "Generate a Box Collider"),
        ('CAPSULE', "Capsule Collider", "Generate a Capsule Collider"),
        ('SPHERE', "Sphere Collider", "Generate a Sphere Collider")
        ],
        default='CONVEX'
    )

    simulation_type: EnumProperty(
        name="Simulation Type",
        items=[
        ('Static', "Static", ""),
        ('Dynamic', "Dynamic", ""),
        ('Kinematic', "Kinematic", "")
        ],
        default='Kinematic'
    )

    matchSize: BoolProperty(
        name="Match the Shape of Existing Mesh",
        description="Match the size of the selected Mesh",
        default=True,

    )

    radius: FloatProperty(
        name="Radius",
        description="Enter the Radius value of the capsule",
        default=0,
        min=0,
        max=100,
        step=1,
    )

    height: FloatProperty(
        name="height",
        description="Enter the height of the capsule",
        default=0,
        min=0,
        max=1000,
        step=1,
    )

    sampleverts: IntProperty(
        name="Vertices to Sample",
        description="This is the number of vertices in your new collider",
        default=1,
        min=1,
        max=100,
    )

# anims props"
    frameall: BoolProperty(
        name="All Frames",
        default=False,
        description="Insert a keyframe on every frame of the active action"
    )

    body_list: EnumProperty(
        items=[(name, name, '') for name in cp77riglist(None)[1]],
        name="Rig GLB"
    )

# mesh panel props

    fbx_rot: BoolProperty(
        name="",
        default=False,
        description="Rotate for an fbx orientated mesh"
    )

    refit_json: EnumProperty(
        items=[(target_body_names, target_body_names, '') for target_body_names in CP77RefitList(None)[1]],
        name="Body Shape"
    )

    selected_armature: EnumProperty(
        items=CP77ArmatureList
    )

    mesh_source: EnumProperty(
        items=CP77CollectionList
    )

    mesh_target: EnumProperty(
        items=CP77CollectionList
    )

    merge_distance: FloatProperty(
        name="Merge Distance",
        default=0.0001,
        min=0.0,
        max=1.0
    )

    smooth_factor: FloatProperty(
        name="Smooth Factor",
        default=0.5,
        min=0.0,
        max=1.0
    )

    remap_depot: BoolProperty(
        name="Remap Depot",
        default=False,
        description="replace the json depot path with the one in prefs"
    )

class CP77CollisionGenerator(Operator):
    bl_idname = "generate_cp77.collisions"
    bl_label = "Generate Collider"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Generate Colliders for use with Cyberpunk 2077"



    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        props = context.scene.cp77_panel_props
        CP77CollisionGen(self, context,props.matchSize, props.collision_type, props.collision_shape, props.sampleverts, props.radius, props.height, props.physics_material)
        return {"FINISHED"}

    def draw(self, context):
        props = context.scene.cp77_panel_props
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Collision Type:")
        split.prop(props, 'collision_type', text="")
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Collision Shape:")
        split.prop(props, 'collision_shape', text="")
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
        split.label(text="Material:")
        split.prop(props, 'physics_material', text="")
        row = layout.row(align=True)
        split = row.split(factor=0.5,align=True)
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


class CP77CollisionExport(Operator):
    bl_idname = "export_scene.collisions"
    bl_label = "Export Collisions to .JSON"
    bl_parent_id = "CP77_PT_collisions"
    bl_description = "Export project collisions to .phys.json"

    filepath: StringProperty(subtype="FILE_PATH")

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.cp77_panel_props, "collision_type")

    def execute(self, context):
        collision_type = context.scene.cp77_panel_props.collision_type
        cp77_collision_export(self.filepath, collision_type)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


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

class CP77PhysMatAssign(Operator):
    bl_idname = "object.set_physics_material"
    bl_label = "Set Physics Properties"

    # Need to implement a callback here so that changing the material automatically updates the other properties

    def execute(self, context):
        selected_physmat = context.object["physics_material"]

        # Find the corresponding material data
        physmat_data = next((mat for mat in physmats_data if mat["Name"] == selected_physmat), None)

        if physmat_data is not None:

            # Set custom properties on the object
            obj = context.object
            props = context.scene.cp77_panel_props
            obj['simulationType'] = props.simulation_type
            obj["physics_material"] = props.physics_material
            obj["Density"] = physmat_data.get("Density", 0)
            obj["staticFriction"] = physmat_data.get("staticFriction", 0)
            obj["dynamicFriction"] = physmat_data.get("dynamicFriction", 0)
            obj["restitution"] = physmat_data.get("restitution", 0)
            volume = calculate_mesh_volume(obj)
            obj['volume'] = volume
            # Calculate mass based on density and mesh volume
            mass = obj["Density"] * volume
            obj["Mass"] = mass
            obj['collisionType'] = props.collision_type
            a, b, c = obj.dimensions
            Ix = (1 / 12) * obj["Density"] * volume * (b**2 + c**2)
            Iy = (1 / 12) * obj["Density"] * volume * (a**2 + c**2)
            Iz = (1 / 12) * obj["Density"] * volume * (a**2 + b**2)

            # Set the inertia
            obj["inertia_X"] = Ix
            obj["inertia_Y"] = Iy
            obj["inertia_Z"] = Iz

        return {'FINISHED'}


class CP77_PT_CollisionTools(Panel):
    bl_label = "Collision Tools"
    bl_idname = "CP77_PT_collisions"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = context.preferences.addons[__name__].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'MESH'
        else:
            return context

    def draw(self, context):
        layout = self.layout
        cp77_addon_prefs = context.preferences.addons[__name__].preferences

        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_collisiontools:
                props = context.scene.cp77_panel_props
                box = layout.box()
                row = box.row(align=True)
                row.operator("generate_cp77.collisions")
                row = box.row(align=True)
                row.operator("import_scene.phys")
                row = box.row(align=True)
                row.operator("export_scene.collisions")
                obj = context.active_object
                if obj and "collisionType" in obj:
                    box = layout.box()
                    box.label(text='Collision Properties')
                    row = box.row()
                    split = row.split(factor=0.3,align=True)
                    split.label(text='Type:')
                    split.prop(props, 'collision_type', text="")
                    row = box.row()
                    split = row.split(factor=0.5,align=True)
                    split.label(text="simulationType")
                    split.prop(props, 'simulation_type', text="")
                    row = box.row()
                    split = row.split(factor=0.3,align=True)
                    split.label(text='Material:')
                    split.prop(props, 'physics_material', text="")
                    row = box.row()
                    row.label(text=f"Mass: {obj.get('Mass', 0):.2f}")
                    row = box.row()
                    row.alignment = 'LEFT'
                    col = row.column(align=True)
                    col.label(text='Inertia:')
                    row = box.row()
                    row.alignment = 'CENTER'
                    col = row.column(align=True)
                    split = col.split(factor=0.33,align=True)
                    split.label(text=f"X: {obj.get('inertia_X', 0):.0f}")
                    split.label(text=f"Y: {obj.get('inertia_Y', 0):.0f}")
                    split.label(text=f"Z: {obj.get('inertia_Z', 0):.0f}")
                    row = box.row()
                    row.operator('object.set_physics_material')


def CP77AnimsList(self, context):
    for action in bpy.data.actions:
        if action.library:
            continue
        yield action


### allow deleting animations from the animset panel, regardless of editor context
class CP77AnimsDelete(Operator):
    bl_idname = 'cp77.delete_anims'
    bl_label = "Delete action"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Delete this action"

    name: StringProperty()

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.animation_data

    def execute(self, context):
        delete_anim(self, context)
        return{'FINISHED'}


# this class is where most of the function is so far - play/pause
# Todo: fix renaming actions from here
class CP77Animset(Operator):
    bl_idname = 'cp77.set_animset'
    bl_label = "Available Animsets"
    bl_options = {'INTERNAL', 'UNDO'}

    name: StringProperty(options={'HIDDEN'})
    new_name: StringProperty(name="New name", default="")
    play: BoolProperty(options={'HIDDEN'}, default=False)

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
            return context.window_manager.invoke_props_dialog(self)
        else:
            self.new_name = ""
            return self.execute(context)



class CP77BoneHider(Operator):
    bl_idname = "bone_hider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"
    bl_description = "Hide deform bones in the selected armature"

    def execute(self, context):
        hide_extra_bones(self, context)
        return{'FINISHED'}


class CP77BoneUnhider(Operator):
    bl_idname = "bone_unhider.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_options = {'REGISTER', 'UNDO'}
    bl_label = "Toggle Deform Bone Visibilty"
    bl_description = "Unhide deform bones in the selected armature"

    def execute(self, context):
        unhide_extra_bones(self, context)
        return{'FINISHED'}


# inserts a keyframe on the current frame
class CP77Keyframe(Operator):
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


class CP77ResetArmature(Operator):
    bl_idname = "reset_armature.cp77"
    bl_parent_id = "CP77_PT_animspanel"
    bl_label = "Reset Armature Position"
    bl_description = "Clear all transforms on current selected armature"

    def execute(self, context):
        reset_armature(self, context)
        return {"FINISHED"}


class CP77NewAction(Operator):

    bl_idname = 'cp77.new_action'
    bl_label = "Add Action"
    bl_options = {'INTERNAL', 'UNDO'}
    bl_description = "Add a new action to the list"

    name: StringProperty(default="New action")

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


class CP77RigLoader(Operator):
    bl_idname = "cp77.rig_loader"
    bl_label = "Load rigs from .glb"
    bl_description = "Load Cyberpunk 2077 deform rigs from plugin resources"

    files: CollectionProperty(type=OperatorFileListElement)
    appearances: StringProperty(name="Appearances", default="")
    directory: StringProperty(name="Directory", default="")
    filepath: StringProperty(name="Filepath", default="")

    def execute(self, context):
        props = context.scene.cp77_panel_props
        selected_rig_name = props.body_list
        rig_files, rig_names = cp77riglist(context)

        if selected_rig_name in rig_names:
            # Find the corresponding .glb file and load it
            selected_rig = rig_files[rig_names.index(selected_rig_name)]
            self.filepath = selected_rig
            CP77GLBimport(self, exclude_unused_mats=True, image_format='PNG', with_materials=False,
                          filepath=selected_rig, hide_armatures=False, import_garmentsupport=False, files=[], directory='', appearances="ALL", remap_depot=False)
            if props.fbx_rot:
                rotate_quat_180(self,context)
        return {'FINISHED'}


### Draw a panel to store anims functions
class CP77_PT_AnimsPanel(Panel):
    bl_idname = "CP77_PT_animspanel"
    bl_label = "Animation Tools"
    bl_category = "CP77 Modding"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_options = {'DEFAULT_CLOSED'}

    name: StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = context.preferences.addons[__name__].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'ARMATURE'
        else:
            return context

## make sure the context is unrestricted as possible, ensure there's an armature selected
    def draw(self, context):
        layout = self.layout

        cp77_addon_prefs = context.preferences.addons[__name__].preferences

        if cp77_addon_prefs.show_animtools:
            props = context.scene.cp77_panel_props
            box = layout.box()
            box.label(text='Rigs', icon_value=custom_icon_col["import"]['WKIT'].icon_id)
            row = box.row(align=True)
            row.label(text='Rig:')
            row.prop(props, 'body_list', text="",)
            row = box.row(align=True)
            row.operator('cp77.rig_loader',icon='ADD', text="Load Selected Rig")
            row.prop(props, 'fbx_rot', text="", icon='LOOP_BACK', toggle=1)
            obj = context.active_object
            if obj and obj.type == 'ARMATURE':
                row = box.row(align=True)
                if 'deformBonesHidden' in obj:
                    row.operator('bone_unhider.cp77',text='Unhide Deform Bones')
                else:
                    row.operator('bone_hider.cp77',text='Hide Deform Bones')
                row = box.row(align=True)
                row.operator('reset_armature.cp77')
                available_anims = list(CP77AnimsList(context,obj))
                active_action = obj.animation_data.action if obj.animation_data else None
                if not available_anims:
                    box = layout.box()
                    row = box.row(align=True)
                    row.label(text='Animsets', icon_value=custom_icon_col["import"]['WKIT'].icon_id)
                    row.operator('cp77.new_action',icon='ADD', text="")
                    row = box.row(align=True)
                    row.operator('insert_keyframe.cp77')
                if available_anims:
                    box = layout.box()
                    for action in available_anims:
                        action.use_fake_user:True
                        selected = action == active_action
                        if selected:
                            row = box.row(align=True)
                            row.alignment='CENTER'
                            row.operator("screen.frame_jump", text="", icon='REW').end = False
                            row.operator("screen.keyframe_jump", text="", icon='PREV_KEYFRAME').next = False
                            row.operator("screen.animation_play", text="", icon='PLAY_REVERSE').reverse = True
                            row.operator("screen.animation_play", text="", icon='PLAY')
                            row.operator("screen.keyframe_jump", text="", icon='NEXT_KEYFRAME').next = True
                            row.operator("screen.frame_jump", text="", icon='FF').end = True
                            row = box.row(align=True)
                            row.alignment='LEFT'
                            row.prop(active_action, 'use_frame_range', text="Set Range",toggle=1)
                            active_action.use_frame_range: True
                            if active_action.use_frame_range:
                                row = box.row(align=True)
                                row.prop(active_action, 'frame_start', text="")
                                row.prop(active_action, 'frame_end', text="")
                    row = box.row(align=True)
                    row.operator('insert_keyframe.cp77')

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
                                if active_action.use_frame_range:
                                    row.prop(active_action, 'use_cyclic', icon='CON_FOLLOWPATH', text="")
                            else:
                                icon = 'PLAY' if selected else 'TRIA_RIGHT'
                                op = sub.operator('cp77.set_animset', icon=icon, text="", emboss=True)
                                op.name = action.name
                                op.play = True

                                op = row.operator('cp77.set_animset', text=action.name)
                                op.name = action.name
                                op.play = False
                                row.operator('cp77.delete_anims', icon='X', text="").name = action.name


class CollectionAppearancePanel(Panel):
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


class CP77Autofitter(Operator):
    bl_idname = "cp77.auto_fitter"
    bl_label = "Auto Fit"
    bl_description = "Use to automatically fit your mesh to a selection of modified bodies"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        props = context.scene.cp77_panel_props
        target_body_name = props.refit_json
        target_body_paths, target_body_names = CP77RefitList(context)
        refitter = CP77RefitChecker(self, context)

        if target_body_name in target_body_names:
            target_body_path = target_body_paths[target_body_names.index(target_body_name)]
            CP77Refit(context, refitter, target_body_path, target_body_name, props.fbx_rot)

            return {'FINISHED'}


class CP77WeightTransfer(Operator):
    bl_idname = 'cp77.trans_weights'
    bl_label = "Transfer weights from one mesh to another"
    bl_description = "Transfer weights from source mesh to target mesh"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        # Call the trans_weights function with the provided arguments
        result = trans_weights(self, context)
        return {"FINISHED"}


class CP77UVTool(Operator):
    bl_idname = 'cp77.uv_checker'
    bl_label = "UV Checker"
    bl_description = "Apply a texture to assist with UV coordinate mapping"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        CP77UvChecker(self, context)
        return {"FINISHED"}


class CP77UVCheckRemover(Operator):
    bl_idname = 'cp77.uv_unchecker'
    bl_label = "UV Checker"
    bl_description = "revert back to original material"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.object.active_material.name and context.object.active_material.name == 'UV_Checker'

    def execute(self, context):
        CP77UvUnChecker(self, context)
        return {"FINISHED"}


class CP77HairProfileExport(Operator):
    bl_idname = "export_scene.hp"
    bl_label = "Export Hair Profile"
    bl_description ="Generates a new .hp.json in your mod project folder which can be imported in Wolvenkit"
    bl_parent_id = "CP77_PT_MeshTools"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        cp77_hp_export(self.filepath)
        return {"FINISHED"}


class CP77MlSetupExport(Operator):
    bl_idname = "export_scene.mlsetup"
    bl_label = "Export MLSetup"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "EXPERIMENTAL: Export material changes to mlsetup files"

    filepath: StringProperty(subtype="FILE_PATH")

    def execute(self, context):
        cp77_mlsetup_export(self, context)
        return {"FINISHED"}


class CP77SetArmature(Operator):
    bl_idname = "cp77.set_armature"
    bl_label = "Change Armature Target"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Change the armature modifier on selected meshes to the target"

    def execute(self, context):
        CP77ArmatureSet(self,context)
        return {'FINISHED'}


class CP77_OT_submesh_prep(Operator):
# based on Rudolph2109's function
    bl_label = "Prep. It!"
    bl_idname = "cp77.submesh_prep"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_description = "Marking seams based on edges boundary loops, merging vertices, correcting and smoothening the normals based on the direction of the faces"

    def execute(self, context):
        props= context.scene.cp77_panel_props
        CP77SubPrep(self, context, props.smooth_factor, props.merge_distance)
        return {'FINISHED'}


class CP77GroupVerts(Operator):
    bl_idname = "cp77.group_verts"
    bl_parent_id = "CP77_PT_MeshTools"
    bl_label = "Assign to Nearest Group"
    bl_options = {'REGISTER', 'UNDO'}
    bl_description = "Assign ungrouped vertices to their nearest group"

    def execute(self, context):
        CP77GroupUngroupedVerts(self, context)
        return {'FINISHED'}


class CP77RotateObj(Operator):
    bl_label = "Change Orientation"
    bl_idname = "cp77.rotate_obj"
    bl_description = "rotate the selected object"

    def execute(self, context):
        rotate_quat_180(self, context)
        return {'FINISHED'}


class CP77_PT_MeshTools(Panel):
    bl_label = "Mesh Tools"
    bl_idname = "CP77_PT_MeshTools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "CP77 Modding"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        cp77_addon_prefs = context.preferences.addons[__name__].preferences
        if cp77_addon_prefs.context_only:
            return context.active_object and context.active_object.type == 'MESH'
        else:
            return context

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        props = context.scene.cp77_panel_props

        cp77_addon_prefs = context.preferences.addons[__name__].preferences
        if cp77_addon_prefs.show_modtools:
            if cp77_addon_prefs.show_meshtools:
                box.label(text="Mesh Cleanup", icon_value=custom_icon_col["trauma"]["TRAUMA"].icon_id)
                row = box.row(align=True)
                split = row.split(factor=0.7,align=True)
                split.label(text="Merge Distance:")
                split.prop(props,"merge_distance", text="", slider=True)
                row = box.row(align=True)
                split = row.split(factor=0.7,align=True)
                split.label(text="Smooth Factor:")
                split.prop(props,"smooth_factor", text="", slider=True)
                row = box.row(align=True)
                row.operator("cp77.submesh_prep")
                row = box.row(align=True)
                row.operator("cp77.group_verts", text="Group Ungrouped Verts")
                row = box.row(align=True)
                row.operator("cp77.rotate_obj")
                box = layout.box()
                box.label(icon_value=custom_icon_col["sculpt"]["SCULPT"].icon_id, text="Modelling:")
                row = box.row(align=True)
                if context.active_object and context.active_object.type == 'MESH' and context.object.active_material and context.object.active_material.name == 'UV_Checker':
                    row.operator("cp77.uv_unchecker",  text="Remove UV Checker")
                else:
                    row.operator("cp77.uv_checker", text="UV Checker")
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
                box.label(icon_value=custom_icon_col["refit"]["REFIT"].icon_id, text="AKL Autofitter:")
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
                box.operator("export_scene.mlsetup")


## adds a message box for the exporters to use for error notifications, will also be used later for redmod integration
class ShowMessageBox(Operator):
    bl_idname = "cp77.message_box"
    bl_label = "Message"

    message: StringProperty(default="")

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

class CP77StreamingSectorExport(Operator,ExportHelper):
    bl_idname = "export_scene.cp77_sector"
    bl_label = "Export Sector Updates for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export changes to Sectors back to project"
    filename_ext = ".cpmodproj"
    filter_glob: StringProperty(default="*.cpmodproj", options={'HIDDEN'})

    def execute(self, context):
        exportSectors(self.filepath)
        return {'FINISHED'}

class ExportSettings:
    def __init__(self, filepath, export_poses, export_visible, limit_selected, static_prop, red_garment_col):
        self.filepath = filepath
        self.export_poses = export_poses
        self.export_visible = export_visible
        self.limit_selected = limit_selected
        self.static_prop = static_prop
        self.red_garment_col = red_garment_col

class CP77GLBExport(Operator,ExportHelper):
  ### cleaned this up and moved most code to exporters.py
    bl_idname = "export_scene.cp77_glb"
    bl_label = "Export for Cyberpunk"
    bl_options = {'REGISTER','UNDO'}
    bl_description = "Export to GLB with optimized settings for use with Wolvenkit for Cyberpunk 2077"
    filename_ext = ".glb"
   ### adds a checkbox for anim export settings


    def createExportSettings(self):
        return ExportSettings(
            filepath=self.filepath,
            export_poses=self.export_poses,
            export_visible=self.export_visible,
            limit_selected=self.limit_selected,
            static_prop=self.static_prop,
            red_garment_col=self.red_garment_col
        )

    filter_glob: StringProperty(default="*.glb", options={'HIDDEN'})

    limit_selected: BoolProperty(
        name="Limit to Selected Meshes",
        default=True,
        description="Only Export the Selected Meshes. This is probably the setting you want to use"
    )
    # TODO: This should probably be a button in the mesh tools somewhere, but I needed to add this to 40+ meshes with 5 submeshes each
    # Yes, I was making socks -.-
    red_garment_col: BoolProperty(
        name="Add red GarmentCol layer",
        default=False,
        description="Adds a red GarmentCol layer for all selected meshes. Read https://tinyurl.com/cyberpunkgarmentcol for more info"
    )
    static_prop: BoolProperty(
        name="Export as Static Prop",
        default=False,
        description="No armature export, only use this for exporting props and objects which do not need to move"
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

    def draw(self, context):
        layout = self.layout
        row = layout.row(align=True)
        row.prop(self, "export_poses")
        if self.export_poses:
            return
        row = layout.row(align=True)
        row.prop(self, "limit_selected")
        row = layout.row(align=True)
        row.prop(self, "red_garment_col")
        if not self.limit_selected:
            row = layout.row(align=True)
            row.prop(self, "export_visible")
        else:
            row = layout.row(align=True)
            row.prop(self, "static_prop")

    def execute(self, context):
        export_cyberpunk_glb(context, settings=self.createExportSettings())
        return {'FINISHED'}


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

    use_cycles: BoolProperty(name="Use Cycles",default=True,description="Use Cycles")
    update_gi: BoolProperty(name="Update Global Illumination",default=False,description="Update Cycles global illumination options for transparency fixes and higher quality renders")
    with_materials: BoolProperty(name="With Materials",default=True,description="Import Wolvenkit-exported materials")
    include_collisions: BoolProperty(name="Include Collisions",default=False,description="Use this option to import collision bodies with this entity")
    include_phys: BoolProperty(name="Include .phys Collisions",default=False,description="Use this option if you want to import the .phys collision bodies. Useful for vehicle modding")
    include_entCollider: BoolProperty(name="Include Collision Components",default=False,description="Use this option to import entColliderComponent and entSimpleColliderComponent")
    remap_depot: BoolProperty(name="Remap Depot",default=False,description="replace the json depot path with the one in prefs")
    inColl: StringProperty(name= "Collector to put the imported entity in",
                                description="Collector to put the imported entity in",
                                default='',
                                options={'HIDDEN'})

    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons[__name__].preferences
        layout = self.layout
        row = layout.row(align=True)
        split = row.split(factor=0.45,align=True)
        split.label(text="Ent Appearance:")
        split.prop(self, "appearances", text="")
        row = layout.row(align=True)
        row.prop(self, "use_cycles")
        if self.use_cycles:
            row = layout.row(align=True)
            row.prop(self, "update_gi")
        row = layout.row(align=True)
        row.prop(self, "with_materials")
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(self,"remap_depot")
        row = layout.row(align=True)
        if not self.include_collisions:
            row.prop(self, "include_collisions")
        if self.include_collisions:
            if not hasattr(self, "_collisions_initialized") or not self._collisions_initialized:
                self.include_phys = True
                self.include_entCollider = True
                self._collisions_initialized = True  # Flag to indicate initialization
            row.prop(self, "include_collisions")
            row = layout.row(align=True)
            row.prop(self, "include_phys")
            row = layout.row(align=True)
            row.prop(self, "include_entCollider")


    def execute(self, context):
        SetCyclesRenderer(self.use_cycles, self.update_gi)

        apps=self.appearances.split(",")
        print('apps - ',apps)
        excluded=""
        bob=self.filepath
        inColl=self.inColl
        #print('Bob - ',bob)
        importEnt( bob, apps, excluded,self.with_materials, self.include_collisions, self.include_phys, self.include_entCollider, inColl, self.remap_depot)

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
    with_materials: BoolProperty(name="With Materials",default=False,description="Import Wolvenkit-exported materials")
    with_lights: BoolProperty(name="With Lights",default=False,description="Import Lights from the sector")
    remap_depot: BoolProperty(name="Remap Depot",default=False,description="replace the json depot path with the one in prefs")


    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons[__name__].preferences
        layout = self.layout
        box = layout.box()
        row = box.row(align=True)
        row.prop(self, "want_collisions",)
        row = layout.row(align=True)
        row.prop(self, "am_modding")
        row = layout.row(align=True)
        row.prop(self, "with_materials")
        row = layout.row(align=True)
        row.prop(self, "with_lights")
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(self,"remap_depot")

    def execute(self, context):
        bob=self.filepath
        print('Importing Sectors from project - ',bob)
        importSectors( bob, self.want_collisions, self.am_modding, self.with_materials , self.remap_depot, self.with_lights)
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
        operator = context.space_data.active_operator
        self.layout.prop(operator, "with_materials", text="")

    def draw(self, context):
        cp77_addon_prefs = bpy.context.preferences.addons[__name__].preferences
        props = context.scene.cp77_panel_props
        operator = context.space_data.active_operator
        layout = self.layout
        row = layout.row(align=True)
        layout.enabled = operator.with_materials
        row.prop(operator, 'exclude_unused_mats')
        row = layout.row(align=True)
        row.prop(operator, 'image_format')
        row = layout.row(align=True)
        row.prop(operator, 'hide_armatures')
        row = layout.row(align=True)
        row.prop(operator, 'use_cycles')
        if cp77_addon_prefs.experimental_features:
            row = layout.row(align=True)
            row.prop(props,"remap_depot")
        if operator.use_cycles:
            row = layout.row(align=True)
            row.prop(operator, 'update_gi')
        row = layout.row(align=True)
        row.prop(operator, 'import_garmentsupport')


class CP77Import(Operator,ImportHelper):
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

    use_cycles: BoolProperty(name="Use Cycles",default=True,description="Use Cycles higher quality renders")

    update_gi: BoolProperty(name="Update Global Illumination",default=False,description="Update Cycles global illumination options for transparency fixes and higher quality renders")

    import_garmentsupport: BoolProperty(name="Import Garment Support (Experimental)",default=True,description="Imports Garment Support mesh data as color attributes")

    remap_depot: BoolProperty(name="Remap Depot",default=False,description="replace the json depot path with the one in prefs")

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
        SetCyclesRenderer(self.use_cycles, self.update_gi)
        props = context.scene.cp77_panel_props
        CP77GLBimport(self, self.exclude_unused_mats, self.image_format, self.with_materials, self.filepath, self.hide_armatures, self.import_garmentsupport, self.files, self.directory, self.appearances, props.remap_depot)

        return {'FINISHED'}

def menu_func_import(self, context):
    self.layout.operator(CP77Import.bl_idname, text="Cyberpunk GLTF (.gltf/.glb)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77EntityImport.bl_idname, text="Cyberpunk Entity (.json)", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77StreamingSectorImport.bl_idname, text="Cyberpunk StreamingSector", icon_value=custom_icon_col["import"]['WKIT'].icon_id)

def menu_func_export(self, context):
    self.layout.operator(CP77GLBExport.bl_idname, text="Cyberpunk GLB", icon_value=custom_icon_col["import"]['WKIT'].icon_id)
    self.layout.operator(CP77StreamingSectorExport.bl_idname, text="Cyberpunk StreamingSector", icon_value=custom_icon_col["import"]['WKIT'].icon_id)

#kwekmaster - Minor Refactoring
classes = (
    CP77Import,
    CP77EntityImport,
    CP77_PT_ImportWithMaterial,
    CP77StreamingSectorImport,
    CP77StreamingSectorExport,
    CP77GLBExport,
    ShowMessageBox,
    CP77_PT_AnimsPanel,
    CP77Keyframe,
    CP77CollisionExport,
    CP77CollisionGenerator,
    CP77Animset,
    CP77ScriptManager,
    CP77DeleteScript,
    CP77CreateScript,
    CP77LoadScript,
    CP77AnimsDelete,
    CP77SaveScript,
    CP77IOSuitePreferences,
    CollectionAppearancePanel,
    CP77HairProfileExport,
    CP77RotateObj,
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
    CP77UVCheckRemover,
    CP7PhysImport,
    CP77PhysMatAssign,
    CP77_PT_CollisionTools,
    CP77_OT_submesh_prep,
    CP77BoneHider,
    CP77BoneUnhider,
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

    Scene.cp77_panel_props = PointerProperty(type=CP77_PT_PanelProps)
    TOPBAR_MT_file_import.append(menu_func_import)
    TOPBAR_MT_file_export.append(menu_func_export)

def unregister():
    del Scene.cp77_panel_props
    for icon_key in custom_icon_col.keys():
        bpy.utils.previews.remove(custom_icon_col[icon_key])


    #kwekmaster - Minor Refactoring
    for cls in classes:
        bpy.utils.unregister_class(cls)


    TOPBAR_MT_file_import.remove(menu_func_import)
    TOPBAR_MT_file_export.remove(menu_func_export)
    custom_icon_col.clear()

if __name__ == "__main__":
    register()
