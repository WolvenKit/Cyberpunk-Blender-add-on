import bpy
import os
from bpy.types import (PropertyGroup, Scene, Object)
from bpy.props import (StringProperty, EnumProperty, BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty)
from .main.physmat_lib import physmat_list
#from . meshtools import (CP77CollectionList)
from .icons.cp77_icons import get_icon
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
    Adonis = os.path.join(refit_dir, "adonis_autofitter.npz")
    VanillaFemToMasc = os.path.join(refit_dir, "vanilla_femtomasc_autofitter.npz")
    VanillaFem_BigBoobs = os.path.join(refit_dir, "f_normal_to_big_boobs_autofitter.npz")
    VanillaFem_SmallBoobs = os.path.join(refit_dir, "f_normal_to_small_boobs_autofitter.npz")
    VanillaMascToFem = os.path.join(refit_dir, "vanilla_masctofem_autofitter.npz")
    Lush = os.path.join(refit_dir, "lush_autofitter.npz")
    Hyst_RB = os.path.join(refit_dir, "hyst_rb_autofitter.npz")
    Hyst_EBB = os.path.join(refit_dir, "hyst_ebb_autofitter.npz")
    Hyst_EBB_RB = os.path.join(refit_dir, "hyst_ebb_rb_autofitter.npz")
    Flat_Chest = os.path.join(refit_dir, "na_flatchest_autofitter.npz")
    Solo_Ultimate = os.path.join(refit_dir, "soloultimate_autofitter.npz")
    Gymfiend = os.path.join(refit_dir, "gymfiend_autofitter.npz")
    Fryja = os.path.join(refit_dir, "fryja _autofitter.npz")
    Elegy = os.path.join(refit_dir, "elegy_autofitter.npz")

    # Return the list of variable names
    target_body_paths = [ none, Gymfiend, Fryja, Solo_Ultimate, Adonis, Flat_Chest, Hyst_EBB_RB, Hyst_EBB, Hyst_RB, Lush, VanillaFemToMasc, VanillaMascToFem, VanillaFem_BigBoobs, VanillaFem_SmallBoobs, Elegy ]
    target_body_names = [ 'None', 'Gymfiend', 'Fryja', 'Solo_Ultimate', 'Adonis', 'Flat_Chest', 'Hyst_EBB_RB', 'Hyst_EBB', 'Hyst_RB', 'Lush', 'VanillaFemToMasc', 'VanillaMascToFem', 'VanillaFem_BigBoobs', 'VanillaFem_SmallBoobs', 'Elegy']

    # Return the list of tuples
    return target_body_paths, target_body_names

def CP77RefitAddonList(context):

    SoloArmsAddon = os.path.join(refit_dir, "addon_solo_arms.npz")
    Hyst_EBBP_Addon = os.path.join(refit_dir, "addon_hyst_ebbp.npz")
    Hyst_EBBN_Addon = os.path.join(refit_dir, "addon_hyst_ebbn.npz")

    # Return the list of variable names
    addon_target_body_paths = [SoloArmsAddon, Hyst_EBBP_Addon, Hyst_EBBN_Addon]
    addon_target_body_names = ['SoloArmsAddon','Hyst_EBBP_Addon', 'Hyst_EBBN_Addon']

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
        ('WORLD', "worldCollisionNode", "Generate worldCollisionNode"),
        ('TERRAIN', "worldTerrainCollisionNode", "Generate sector with a worldTerrainCollisionNode")
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

    animtab: EnumProperty(
        name="Animation Tab",
        items=[
            ('RIGSETUP', "Rig Setup", "Rig loading and configuration tools"),
            ('ANIMATION', "Animation", "Animation playback and keyframing tools"),
            ('FACIAL', "Facial", "Facial animation setup and baking tools"),
        ],
        default='ANIMATION'
    )

    active_action_index: IntProperty(
        name="Active Action Index",
        default=0
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
    action["numExtraTracks"] = num_extra_tracks
    action["constTrackKeys"] = const_track_keys
    action["trackKeys"] = track_keys
    action["fallbackFrameIndices"] = fallback_frame_indices
    action["optimizationHints"] = optimizationHints
    #action["maxRotationCompression"] = optimizationHints['maxRotationCompression']

    # Animation events (V5+)
    anim_events = extras.get("animEvents", None)
    if anim_events is not None:
        action["animEvents"] = anim_events

    # Populate the CollectionProperty + markers from the IDProperty
    try:
        from .animtools.anim_events import load_events_to_collection
        load_events_to_collection(action)
    except Exception as e:
        print(f"[CP77] Warning: could not load animation events for '{action.name}': {e}")


def add_skin_props(gltf_skin, armature_obj):
    """Transfer glTF skin extras to Blender Armature custom properties.

    Captures from the skin's extras dict:
      - rigPath          → armature["rigPath"]  (string)
      - boneNames        → armature["boneNames"]  (list, stored as single property)
      - boneParentIndexes → armature["boneParentIndexes"]  (list, stored as single property)
      - trackNames       → armature["trackNames"]  (dict, {"0": name, "1": name, …})

    Compatible with Blender 4.x and 5.x.
    """
    if armature_obj is None or armature_obj.type != 'ARMATURE':
        return

    extras = getattr(gltf_skin, 'extras', {})
    if not extras:
        return

    # rigPath — single string
    rig_path = extras.get("rigPath", "")
    armature_obj["rigPath"] = rig_path

    # boneNames — entire list as one IDProperty array
    bone_names = extras.get("boneNames", [])
    if bone_names:
        armature_obj["boneNames"] = list(bone_names)

    # boneParentIndexes — entire list as one IDProperty array
    bone_parent_indexes = extras.get("boneParentIndexes", [])
    if bone_parent_indexes:
        armature_obj["boneParentIndexes"] = list(bone_parent_indexes)

    # trackNames — single dict property {index_str: name}
    track_names = extras.get("trackNames", [])
    if track_names:
        armature_obj["trackNames"] = {str(i): name for i, name in enumerate(track_names)}


def get_track_names(armature_obj):
    """Reconstruct the trackNames list from the armature dict property.

    Supports both the current single-dict format (``armature["trackNames"]``)
    and the legacy per-index format (``armature["trackName_0"]``, …) for
    backward compatibility with older imports.
    """
    # Current format: single dict {"0": name, "1": name, …}
    tn = armature_obj.get("trackNames")
    if tn is not None and hasattr(tn, 'keys'):
        n = len(tn)
        return [str(tn.get(str(i), "")) for i in range(n)]

    # Legacy format: numTrackNames + trackName_{i}
    count = armature_obj.get("numTrackNames", 0)
    if count > 0:
        return [armature_obj.get(f"trackName_{i}", "") for i in range(count)]

    return []
def get_preview_parts(self, context):
    from .icons.cp77_icons import get_icon
    return [
        ('face', "Face", "Face poses", get_icon('FACE'), 0),
        ('eyes', "Eyes", "Eye poses", get_icon('EYES'), 1),
        ('tongue', "Tongue", "Tongue poses", get_icon('TONGUE'), 2),
        ]
class CP77_FacialProps(PropertyGroup):
    rig_json: StringProperty(
            name="Rig JSON",
            subtype='FILE_PATH',
            description="Path to *_skeleton_rig.json file"
            )
    facial_json: StringProperty(
            name="FacialSetup JSON",
            subtype='FILE_PATH',
            description="Path to *_facialsetup.json file"
            )
    main_pose: IntProperty(
            name="Main Pose",
            default=1,
            min=1,
            max=133,
            step=1,
            description="Select main pose to preview (1-133)"
            )
    preview_weight: FloatProperty(
            name="Weight",
            default=1.0,
            min=0.0,
            max=2.0,
            description="Pose weight for preview"
            )

    preview_part: EnumProperty(
        name = "Part",
        description = "Which set of main poses to browse",
        items = get_preview_parts,
    )

    preview_pose_index: IntProperty(
        name = "Pose Index",
        description = "Index into the selected part's main pose list",
        default = 0,
        min = 0,
        max = 255,   # clamped at runtime by _get_pose_count()
    )  # type: ignore

    preview_active: BoolProperty(
        name = "Preview Active",
        description = "True while a pose preview snapshot is held",
        default = False,
    )  # type: ignore

    solver_active: BoolProperty(
        name = "Solver Active",
        description = "Run the Sermo facial solver every frame change",
        default = False,
    )  # type: ignore
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

class RootMotionData(PropertyGroup):
    hip: StringProperty(
        name="Hip Bone",
        description="Bone containing character hip motion",
        default=""
    )
    root: StringProperty(
        name="Root Bone",
        description="Root bone for motion transfer",
        default=""
    )
    step: IntProperty(
        name="Step Size",
        description="Keyframe interval (1=every frame, higher=faster but less smooth)",
        default=3, min=1, max=10, soft_max=5
    )
    no_rot: BoolProperty(
        name="Ignore Rotation",
        description="Transfer position only",
        default=False
    )
    do_vert: BoolProperty(
        name="Extract Vertical Motion",
        description="Include Z-axis motion",
        default=False
    )

operators, other_classes = get_classes(sys.modules[__name__])

def register_props():
    for cls in operators:
        bpy.utils.register_class(cls)
    for cls in other_classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.cp77_facial = bpy.props.PointerProperty(type=CP77_FacialProps)
    Scene.cp77_panel_props = PointerProperty(type=CP77_PT_PanelProps)
    Scene.rm_data = PointerProperty(type=RootMotionData)
    update_presets_items()

def unregister_props():
    if hasattr(bpy.types.Scene, "rm_data"):
        del Scene.rm_data
    if hasattr(bpy.types.Scene, "cp77_panel_props"):
        del Scene.cp77_panel_props
    if hasattr(bpy.types.Scene, 'cp77_facial'):
        del bpy.types.Scene.cp77_facial
    for cls in reversed(other_classes):
        bpy.utils.unregister_class(cls)
    for cls in reversed(operators):
        bpy.utils.unregister_class(cls)


