import bpy
import os
from bpy.types import (PropertyGroup, Scene, Object)
from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty)
from .main.physmat_lib import physmat_list
#from . meshtools import (CP77CollectionList)
from .main.common import get_classes, get_rig_dir, get_refit_dir, get_resources_dir, update_presets_items
import sys

resources_dir = get_resources_dir()
refit_dir = get_refit_dir()
rig_dir = get_rig_dir()
physmats_data = physmat_list()
enum_items = [(mat.get("Name", ""), mat.get("Name", ""), "") for mat in physmats_data]


def CP77animBones():
    return ["Hips", "Spine", "Spine1", "Spine2", "Spine3", "LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand", "WeaponLeft", "LeftInHandThumb", "LeftHandThumb1", "LeftHandThumb2", "LeftInHandIndex", "LeftHandIndex1", "LeftHandIndex2", "LeftHandIndex3", "LeftInHandMiddle", "LeftHandMiddle1", "LeftHandMiddle2", "LeftHandMiddle3", "LeftInHandRing", "LeftHandRing1", "LeftHandRing2", "LeftHandRing3", "LeftInHandPinky", "LeftHandPinky1", "LeftHandPinky2", "LeftHandPinky3", "RightShoulder", "RightArm", "RightForeArm", "RightHand", "WeaponRight", "RightInHandThumb", "RightHandThumb1", "RightHandThumb2", "RightInHandIndex", "RightHandIndex1", "RightHandIndex2", "RightHandIndex3", "RightInHandMiddle", "RightHandMiddle1", "RightHandMiddle2", "RightHandMiddle3", "RightInHandRing", "RightHandRing1", "RightHandRing2", "RightHandRing3", "RightInHandPinky", "RightHandPinky1", "RightHandPinky2", "RightHandPinky3", "Neck", "Neck1", "Head", "LeftEye", "RightEye", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftHeel", "LeftToeBase", "RightUpLeg", "RightLeg", "RightFoot", "RightHeel", "RightToeBase"]


def CP77RefitList(context):
    none = None
    Adonis = os.path.join(refit_dir, "adonis.refitter.npz")
    VanillaFemToMasc = os.path.join(refit_dir, "f2m.refitter.npz")
    VanillaFem_BigBoobs = os.path.join(refit_dir, "f_normal_to_big_boobs.refitter.npz")
    VanillaFem_SmallBoobs = os.path.join(refit_dir, "f_normal_to_small_boobs.refitter.npz")
    VanillaMascToFem = os.path.join(refit_dir, "m2f.refitter.npz")
    Lush = os.path.join(refit_dir, "lush.refitter.npz")
    Hyst_RB = os.path.join(refit_dir, "hyst_rb.refitter.npz")
    Hyst_EBB = os.path.join(refit_dir, "hyst_ebb.refitter.npz")
    Hyst_EBB_RB = os.path.join(refit_dir, "hyst_ebb_rb.refitter.npz")
    Flat_Chest = os.path.join(refit_dir, "flat_chest.refitter.npz")
    Solo_Ultimate = os.path.join(refit_dir, "solo_ultimate.refitter.npz")
    Gymfiend = os.path.join(refit_dir, "gymfiend.refitter.npz")
    Freyja = os.path.join(refit_dir, "freyja.refitter.npz")

    # Return the list of variable names
    target_body_paths = [ none, Gymfiend, Freyja, Solo_Ultimate, Adonis, Flat_Chest, Hyst_EBB_RB, Hyst_EBB, Hyst_RB, Lush, VanillaFemToMasc, VanillaMascToFem, VanillaFem_BigBoobs, VanillaFem_SmallBoobs ]
    target_body_names = [ 'None', 'Gymfiend', 'Freyja', 'Solo_Ultimate', 'Adonis', 'Flat_Chest', 'Hyst_EBB_RB', 'Hyst_EBB', 'Hyst_RB', 'Lush', 'VanillaFemToMasc', 'VanillaMascToFem', 'VanillaFem_BigBoobs', 'VanillaFem_SmallBoobs' ]

    # Return the list of tuples
    return target_body_paths, target_body_names

def CP77RefitAddonList(context):

    SoloArmsAddon = os.path.join(refit_dir, "SoloArmsAddon.refitter.zip")
    Hyst_EBBP_Addon = os.path.join(refit_dir, "hyst_ebbp_addon.refitter.zip")

    # Return the list of variable names
    addon_target_body_paths = [SoloArmsAddon, Hyst_EBBP_Addon]
    addon_target_body_names = ['SoloArmsAddon','Hyst_EBBP_Addon']

    # Return the list of tuples
    return addon_target_body_paths, addon_target_body_names


def SetCyclesRenderer(use_cycles=True, set_gi_params=False):
    # set the render engine for all scenes to Cycles

    if use_cycles:
        for scene in bpy.data.scenes:
            scene.render.engine = 'CYCLES'
            scene.cycles.device = 'GPU'

        if set_gi_params:
            cycles = bpy.context.scene.cycles
            cycles.transparent_max_bounces = 40

def SetVulkanBackend(use_vulkan=True):

    if use_vulkan:
        system_prefs = bpy.context.preferences.system
        system_prefs.gpu_backend = 'VULKAN'

def CP77CollectionList(self, context):
    items = []
    excluded_names = ["Collection", "Scene Collection", "glTF_not_exported"]

    for collection in bpy.data.collections:
        if collection.name not in excluded_names:
        ## make sure the collection has meshes in it
            if any(obj.type == 'MESH' for obj in collection.objects):
                items.append((collection.name, collection.name, ""))
    return items

def cp77riglist(self, context):
    cp77rigs = []
    man_base = os.path.join(rig_dir, "man_base_full.glb")
    woman_base = os.path.join(rig_dir, "woman_base_full.glb")
    man_big = os.path.join(rig_dir, "man_big_full.glb")
    man_fat = os.path.join(rig_dir, "man_fat_full.glb")
    Judy = os.path.join(rig_dir, "judy_full.glb")
    Songbird = os.path.join(rig_dir, "songbird_full.glb")
    Panam = os.path.join(rig_dir, "panam_full.glb")
    Jackie = os.path.join(rig_dir, "jackie_full.glb")
    Rhino = os.path.join(rig_dir, "rhino_full.glb")
    Dex = os.path.join(rig_dir, "dex_full.glb")
    Smasher = os.path.join(rig_dir, "smasher_full.glb")

    # Store the variable names in a list
    cp77rigs = [man_base, woman_base, man_big, man_fat, Judy, Songbird, Panam, Jackie, Rhino, Dex, Smasher]
    cp77rig_names = ['man_base', 'woman_base', 'man_big', 'man_fat', 'Judy', 'Songbird', 'Panam', 'Jackie', 'Rhino', 'Dex', 'Adam Smasher']

    # Return the list of variable names
    return cp77rigs, cp77rig_names

def CP77ArmatureList(self, context):
    try:
        arms = [(obj.name, obj.name, "") for obj in bpy.data.objects if obj.type == 'ARMATURE']
    except AttributeError as e:
        print(f"Error accessing bpy.data.objects: {e}")
        arms = []
    return arms


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

    vertex_color_presets: EnumProperty(
        name="Vertex Color Preset",
        items=lambda self, context: update_presets_items() or [(name, name, "") for name in get_colour_presets().keys()]
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
        default='Static'
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
        max=400,
    )

# anims props"
    frameall: BoolProperty(
        name="All Frames",
        default=False,
        description="Insert a keyframe on every frame of the active action"
    )

    body_list: EnumProperty(
        items=[(name, name, '') for name in cp77riglist(None, None)[1]],
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

    refit_addon_json: EnumProperty(
        items=[(addon_target_body_names, addon_target_body_names, '') for addon_target_body_names in CP77RefitAddonList(None)[1]],
        name="Refitter Addon"
    )

    selected_armature: EnumProperty(
        name="Armatures",
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

    use_cycles: BoolProperty(
        name="Set Render Engine to Cycles",
        default=False,
        description="Sets the Render Engine to Cycles. Imported shaders may fail to compile while using EEVEE without the Vulkan backend"
    )

    use_vulkan: BoolProperty(
        name="Set Backend to Vulkan",
        default=True,
        description="""(Requires Restart) Sets the Blender graphics backend to Vulkan which can compile shaders that fail using OpenGL.
This setting can also be changed from within system preferences."""
    )

    update_gi: BoolProperty(
        name="Increase Transparent Light Paths",
        default=False,
        description="Increase Cycles maximum bounces for transparent light paths. This improves shading of layered meshes with alpha such as hair."
    )

    with_materials: BoolProperty(
        name="With Materials",
        default=True,
        description="Import WolvenKit-exported materials"
    )

    axl_yaml: BoolProperty(
        name="Use YAML instead of JSON",
        default=False,
        description="Use the ArchiveXL YAML format instead of JSON format for generated .xl files"
    )

# MLSETUP export props

    write_mltemplate: BoolProperty(
        name="Generate modified MLTEMPLATE",
        default=False,
        description="""WARNING! Can overwrite WolvenKit project files!
Write a MLTEMPLATE json with additional ColorScale overrides to the WolvenKit project when unique ColorScale values are detected"""
    )

def add_anim_props(animation, action):

    extras = getattr(animation, 'extras', {})
    if not extras:
        return
    # Extract properties from animation
    schema = extras.get("schema", "")
    animation_type = extras.get("animationType", "")
    rootMotion_type = extras.get("rootMotionType","")
    frame_clamping = extras.get("frameClamping", False)
    frame_clamping_start_frame = extras.get("frameClampingStartFrame", -1)
    frame_clamping_end_frame = extras.get("frameClampingEndFrame", -1)
    num_extra_joints = extras.get("numExtraJoints", 0)
    num_extra_tracks = extras.get("numExtraTracks", 0)  # Corrected typo in the key name
    const_track_keys = extras.get("constTrackKeys", [])
    track_keys = extras.get("trackKeys", [])
    fallback_frame_indices = extras.get("fallbackFrameIndices", [])
    optimizationHints = extras.get("optimizationHints", [])

    # Add properties to the action
    action["schema"] = schema
   # action["schemaVersion"] = schema['version']
    action["animationType"] = animation_type
    action["rootMotionType"] = rootMotion_type
    action["frameClamping"] = frame_clamping
    action["frameClampingStartFrame"] = frame_clamping_start_frame
    action["frameClampingEndFrame"] = frame_clamping_end_frame
    action["numExtraJoints"] = num_extra_joints
    action["numeExtraTracks"] = num_extra_tracks
    action["constTrackKeys"] = const_track_keys
    action["trackKeys"] = track_keys
    action["fallbackFrameIndices"] = fallback_frame_indices
    action["optimizationHints"] = optimizationHints
    #action["maxRotationCompression"] = optimizationHints['maxRotationCompression']


operators, other_classes = get_classes(sys.modules[__name__])


def register_props():
    for cls in operators:
        bpy.utils.register_class(cls)
    for cls in other_classes:
        bpy.utils.register_class(cls)
    Scene.cp77_panel_props = PointerProperty(type=CP77_PT_PanelProps)
    update_presets_items()

def unregister_props():
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)
    del Scene.cp77_panel_props
