<<<<<<< Updated upstream
=======
import math
>>>>>>> Stashed changes
import sys
import time

import bpy
<<<<<<< Updated upstream
from bpy.props import (
    BoolProperty, CollectionProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty,
    StringProperty,
    )
from bpy.types import (Object, PropertyGroup, Scene)
=======
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty
from bpy.types import PropertyGroup, Scene

from .animtools.runtime.read_models import bundled_rig_items
from .core.registration import RegistrationLedger, get_classes
from .meshtools.refit_catalog import refitter_enum_items
from .meshtools.vertex_color_presets import preset_enum_items

_ENUM_CACHE_TTL = 2.0
_ENUM_CACHE = {
    "collections": {"expires": 0.0, "signature": None, "items": ()},
    "armatures": {"expires": 0.0, "signature": None, "items": ()},
}
_EXCLUDED_COLLECTION_NAMES = frozenset(
    {
        "Collection",
        "Scene Collection",
        "glTF_not_exported",
    }
)
>>>>>>> Stashed changes

from .registration import get_classes, RegistrationLedger
from .vertex_color_presets import get_color_presets, update_presets_items
from .physics.materials import physics_material_enum_items
from .meshtools.refit_catalog import refitter_enum_items
from .animation.rig.catalog import bundled_rig_enum_items

<<<<<<< Updated upstream
enum_items = physics_material_enum_items()



def SetCyclesRenderer(use_cycles=True, set_gi_params=False):
    """Configures rendering environments across all scenes to utilize the Cycles rendering engine."""
    if use_cycles:
        for scene in bpy.data.scenes:
            scene.render.engine = 'CYCLES'
            scene.cycles.device = 'GPU'

        if set_gi_params:
            cycles = bpy.context.scene.cycles
            cycles.transparent_max_bounces = 40
=======
def _cached_enum_items(cache_name, signature, builder):
    cache = _ENUM_CACHE[cache_name]
    now = time.monotonic()
    if cache["signature"] != signature or now >= cache["expires"]:
        cache["items"] = tuple(builder())
        cache["signature"] = signature
        cache["expires"] = now + _ENUM_CACHE_TTL
    return cache["items"]


def SetCyclesRenderer(use_cycles=True, set_gi_params=False, scene=None):
    """Switch one scene to GPU Cycles and return the changes made"""
    changes = []
    if not use_cycles:
        return changes
    scene = scene or bpy.context.scene
    if scene.render.engine != "CYCLES" or scene.cycles.device != "GPU":
        scene.render.engine = "CYCLES"
        scene.cycles.device = "GPU"
        changes.append(f"Scene '{scene.name}' now renders with Cycles on the GPU")
    if set_gi_params and scene.cycles.transparent_max_bounces != 40:
        scene.cycles.transparent_max_bounces = 40
        changes.append(f"Scene '{scene.name}' transparent light paths increased to 40")
    return changes
>>>>>>> Stashed changes


def SetVulkanBackend(use_vulkan=True):
    """Select the Vulkan GPU backend in the user preferences and return the changes made"""
    if not use_vulkan:
        return []
    system_prefs = bpy.context.preferences.system
    if system_prefs.gpu_backend == "VULKAN":
        return []
    system_prefs.gpu_backend = "VULKAN"
    return ["GPU backend preference set to Vulkan; restart Blender to apply it"]


def CP77CollectionList(self, context):
    """Return mesh collection enum items without rescanning on every panel draw"""
    signature = (len(bpy.data.collections), len(bpy.data.objects))

    def build_items():
        for collection in bpy.data.collections:
            if collection.name in _EXCLUDED_COLLECTION_NAMES:
                continue
            if any(obj.type == "MESH" for obj in collection.objects):
                yield (collection.name, collection.name, "")

<<<<<<< Updated upstream
=======
    return _cached_enum_items("collections", signature, build_items)

>>>>>>> Stashed changes

def CP77ArmatureList(self, context):
    """Return armature enum items without rescanning on every panel draw"""
    signature = len(bpy.data.objects)
    return _cached_enum_items(
        "armatures",
        signature,
        lambda: (
            (obj.name, obj.name, "")
            for obj in bpy.data.objects
            if obj.type == "ARMATURE"
        ),
    )


class CP77_PT_PanelProps(PropertyGroup):
<<<<<<< Updated upstream
    """Property definitions for the main addon UI panel."""

    collision_type: EnumProperty(
            name="Collision Type",
            items=[
                ('VEHICLE', "Vehicle", "Generate .phys formatted collisions for a vehicle mod"),
                ('TERRAIN', "worldTerrainCollisionNode", "Generate sector with a worldTerrainCollisionNode")
                ],
            default='VEHICLE'
            )

    vertex_color_presets: EnumProperty(
            name="Vertex Color Preset",
            items=lambda self, context: update_presets_items() or [(name, name, "") for name in
                                                                   get_color_presets().keys()]
            )

    physics_material: EnumProperty(
            items=enum_items,
            name="Physics Material",
            description="Select the physics material for the object",
            default="None"
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
=======
    """Property definitions for the main addon UI panel"""

    vertex_color_presets: EnumProperty(
        name="Vertex Color Preset",
        items=preset_enum_items,
    )
>>>>>>> Stashed changes

    frameall: BoolProperty(
        name="All Frames",
        default=False,
        description="Insert a keyframe on every frame of the active action",
    )

<<<<<<< Updated upstream
    body_list: EnumProperty(
            items=bundled_rig_enum_items,
            name="Rig GLB"
            )
=======
    body_list: EnumProperty(items=bundled_rig_items, name="Bundled Rig")
>>>>>>> Stashed changes

    fbx_rot: BoolProperty(
        name="", default=False, description="Rotate for an fbx orientated mesh"
    )

<<<<<<< Updated upstream
    refit_json: EnumProperty(
            items=refitter_enum_items(),
            name="Body Shape"
            )

    refit_addon_json: EnumProperty(
            items=refitter_enum_items(addon=True),
            name="Refitter Addon"
            )
=======
    refit_json: EnumProperty(items=refitter_enum_items(), name="Body Shape")

    refit_addon_json: EnumProperty(
        items=refitter_enum_items(addon=True), name="Refitter Addon"
    )
>>>>>>> Stashed changes

    selected_armature: EnumProperty(name="Armatures", items=CP77ArmatureList)

    mesh_source: EnumProperty(items=CP77CollectionList)

    mesh_target: EnumProperty(items=CP77CollectionList)

    merge_distance: FloatProperty(
        name="Merge Distance", default=0.0001, min=0.0, max=1.0
    )

    smooth_factor: FloatProperty(
        name="Smooth Angle",
        description="Edges whose faces meet at a sharper angle than this stay sharp",
        subtype="ANGLE",
        default=0.5,
        min=0.0,
        max=math.pi,
    )

    remap_depot: BoolProperty(
        name="Remap Depot",
        default=False,
        description="replace the json depot path with the one in prefs",
    )

    use_cycles: BoolProperty(
        name="Set Render Engine to Cycles",
        default=False,
        description="Sets the Render Engine to Cycles. Imported shaders may fail to compile while using EEVEE without the Vulkan backend",
    )

    use_vulkan: BoolProperty(
<<<<<<< Updated upstream
            name="Set Backend to Vulkan",
            default=False,
            description="(Requires Restart) Sets the Blender graphics backend to Vulkan which can compile shaders that fail using OpenGL."
            )
=======
        name="Set Backend to Vulkan",
        default=False,
        description="(Requires Restart) Sets the Blender graphics backend to Vulkan which can compile shaders that fail using OpenGL.",
    )
>>>>>>> Stashed changes

    update_gi: BoolProperty(
        name="Increase Transparent Light Paths",
        default=False,
        description="Increase Cycles maximum bounces for transparent light paths. This improves shading of layered meshes with alpha such as hair.",
    )

    with_materials: BoolProperty(
        name="With Materials",
        default=True,
        description="Import WolvenKit-exported materials",
    )

    axl_yaml: BoolProperty(
        name="Use YAML instead of JSON",
        default=False,
        description="Use the ArchiveXL YAML format instead of JSON format for generated .xl files",
    )

    include_heightfields: BoolProperty(
        name="Include Heightfields",
        default=False,
        description="Write each new sector's cooked PhysX heightfield shapes into it as terrain collision nodes",
    )

    write_mltemplate: BoolProperty(
        name="Generate modified MLTEMPLATE",
        default=True,
        description="Write project-local MLTEMPLATE overrides when authored multilayer values do not match an existing named override",
    )

    animtab: EnumProperty(
        name="Animation Tab",
        items=[
            ("RIGSETUP", "Rig Setup", "Rig loading and configuration tools"),
            ("ANIMATION", "Animation", "Animation playback and keyframing tools"),
            ("FACIAL", "Facial", "Facial animation setup and baking tools"),
        ],
        default="ANIMATION",
    )

    def get_meshtab_items(self, context):
        return [
<<<<<<< Updated upstream
            ('UTILITIES', "Utilities", ""),
            ('MODELLING', "Modelling", ""),
            ('CHARACTERS', "Characters", ""),
            ('CLOTH', "Garment", "Garment setup, pinning, simulation, and bake tools"),
            ]

    meshtab: EnumProperty(
            items=get_meshtab_items,
            name="Mesh Tab"
            )

    active_action_index: IntProperty(
            name="Active Action Index",
            default=0
            )


def get_preview_parts(self, context):
    """Generates the UI configuration for previewable facial pose categories."""
    from .icons.cp77_icons import get_icon
    return [
        ('face', "Face", "Face poses", get_icon('FACE'), 0),
        ('eyes', "Eyes", "Eye poses", get_icon('EYES'), 1),
        ('tongue', "Tongue", "Tongue poses", get_icon('TONGUE'), 2),
        ]


class CP77_FacialProps(PropertyGroup):
    """Stores configuration and runtime states for the facial animation tools."""

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
            name="Part",
            description="Which set of main poses to browse",
            items=get_preview_parts,
            )

    preview_pose_index: IntProperty(
            name="Pose Index",
            description="Index into the selected part's main pose list",
            default=0,
            min=0,
            max=255,
            )

    solver_active: BoolProperty(
            name="Solver Active",
            description="Run the Sermo facial solver every frame change",
            default=False,
            )
=======
            ("UTILITIES", "Utilities", ""),
            ("MODELLING", "Modelling", ""),
            ("CHARACTERS", "Characters", ""),
            ("CLOTH", "Garment", "Garment setup, pinning, simulation, and bake tools"),
        ]

    meshtab: EnumProperty(items=get_meshtab_items, name="Mesh Tab")
>>>>>>> Stashed changes


registration_classes = get_classes(sys.modules[__name__])

<<<<<<< Updated upstream

def update_cloth_collider(self, context):
    try:
        from .collisiontools.pxbridge import viz
        viz.invalidate_visualization_cache()
    except Exception:
        pass


AVATAR_REGION_ITEMS = [
    ('TORSO', "Torso", "Chest, spine, and abdomen collision region"),
    ('PELVIS', "Pelvis", "Hip and waist collision region"),
    ('ARM', "Arms", "Upper arm, forearm, and wrist collision region"),
    ('LEG', "Legs", "Thighs, shins, ankles, and feet collision region"),
    ('HEAD', "Head / Neck", "Head and neck collision region"),
    ('CUSTOM', "Custom", "Manually tuned collider"),
    ]

AVATAR_BODY_TYPE_ITEMS = [
    ('CUSTOM', "Custom", "User-authored avatar profile"),
    ('FEM_BASE', "Fem Base", "Cyberpunk base female body"),
    ('MASC_BASE', "Masc Base", "Cyberpunk base male body"),
    ('BIG', "Large Body", "Large or bulky body collision profile"),
    ('THIN', "Slim Body", "Slim body collision profile"),
    ]

AVATAR_FITTING_POSE_ITEMS = [
    ('CURRENT', "Current Pose", "Use the current armature pose for fitting and simulation"),
    ('APOSE', "A-Pose", "Avatar profile was authored for an A-pose"),
    ('TPOSE', "T-Pose", "Avatar profile was authored for a T-pose"),
    ]

AVATAR_STATE_ITEMS = [
    ('DRAFT', "Draft", "Profile is editable but not validated"),
    ('READY', "Ready", "Profile has colliders and can be used for garments"),
    ('ERROR', "Error", "Profile requires attention"),
    ]

AVATAR_ANCHOR_TYPE_ITEMS = [
    ('COLLAR', "Collar", "Neck or collar arrangement anchor"),
    ('SHOULDER', "Shoulder", "Shoulder arrangement anchor"),
    ('CHEST', "Chest", "Front or back chest arrangement anchor"),
    ('WAIST', "Waist", "Waistband arrangement anchor"),
    ('HIP', "Hip", "Hip arrangement anchor"),
    ('WRIST', "Wrist", "Sleeve cuff arrangement anchor"),
    ('ANKLE', "Ankle", "Pant cuff or ankle arrangement anchor"),
    ('CUSTOM', "Custom", "User-defined arrangement anchor"),
    ]


class CP77_ClothColliderProps(PropertyGroup):
    name: StringProperty(default="Collider")
    enabled: BoolProperty(name="Enabled", default=True, update=update_cloth_collider)
    collider_type: EnumProperty(
            name="Type",
            items=[('SPHERE', "Sphere", ""), ('CAPSULE', "Capsule", "")],
            default='SPHERE',
            update=update_cloth_collider
            )
    region: EnumProperty(name="Region", items=AVATAR_REGION_ITEMS, default='CUSTOM', update=update_cloth_collider)
    bone: StringProperty(name="Bone", update=update_cloth_collider)
    target_bone: StringProperty(name="Target Bone", update=update_cloth_collider)
    radius: FloatProperty(name="Radius", default=0.08, min=0.001, update=update_cloth_collider)


class CP77_AvatarAnchorProps(PropertyGroup):
    name: StringProperty(default="Anchor")
    anchor_type: EnumProperty(name="Type", items=AVATAR_ANCHOR_TYPE_ITEMS, default='CUSTOM')
    bone: StringProperty(name="Bone")
    local_pos: FloatVectorProperty(name="Local Position", subtype='TRANSLATION', size=3, default=(0.0, 0.0, 0.0))


class CP77_AvatarProfileProps(PropertyGroup):
    enabled: BoolProperty(name="Enable Avatar Profile", default=True, update=update_cloth_collider)
    profile_name: StringProperty(name="Profile", default="Avatar Profile")
    body_type: EnumProperty(name="Body Type", items=AVATAR_BODY_TYPE_ITEMS, default='CUSTOM')
    fitting_pose: EnumProperty(name="Fitting Pose", items=AVATAR_FITTING_POSE_ITEMS, default='CURRENT')
    body_mesh: PointerProperty(
        name="Body Mesh", type=Object, description="Mesh used as the primary avatar collision shell"
        )
    use_mesh_collision: BoolProperty(name="Use Body Mesh Collision", default=False, update=update_cloth_collider)
    use_primitive_collision: BoolProperty(name="Use Primitive Fallback", default=True, update=update_cloth_collider)
    mesh_collision_skin: FloatProperty(
        name="Mesh Collision Skin", default=0.025, min=0.001, max=0.25, update=update_cloth_collider
        )
    mesh_collision_max_tris: IntProperty(
        name="Mesh Collision Max Tris", default=1500, min=64, max=20000, update=update_cloth_collider
        )
    state: EnumProperty(name="State", items=AVATAR_STATE_ITEMS, default='DRAFT')
    global_inflate: FloatProperty(name="Global Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    torso_inflate: FloatProperty(name="Torso Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    pelvis_inflate: FloatProperty(name="Pelvis Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    arm_inflate: FloatProperty(name="Arm Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    leg_inflate: FloatProperty(name="Leg Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    head_inflate: FloatProperty(name="Head / Neck Inflate", default=0.0, min=0.0, max=0.5, update=update_cloth_collider)
    auto_fit_percentile: FloatProperty(name="Fit Percentile", default=0.55, min=0.1, max=0.98)
    min_radius: FloatProperty(name="Min Radius", default=0.025, min=0.001, max=1.0, update=update_cloth_collider)
    max_radius: FloatProperty(name="Max Radius", default=0.22, min=0.01, max=5.0, update=update_cloth_collider)
    status: StringProperty(name="Status", default="Not validated")
    errors: StringProperty(name="Issues", default="")
    last_sphere_count: IntProperty(name="Spheres", default=0, min=0)
    last_capsule_count: IntProperty(name="Capsules", default=0, min=0)
    last_anchor_count: IntProperty(name="Anchors", default=0, min=0)


GARMENT_TYPE_ITEMS = [
    ('CUSTOM', "Custom", "Generic garment or cloth mesh"),
    ('SHIRT', "Shirt", "Upper-body garment"),
    ('JACKET', "Jacket", "Heavier upper-body garment"),
    ('SKIRT', "Skirt", "Waist-anchored lower-body garment"),
    ('CAPE', "Cape", "Shoulder or neck anchored loose garment"),
    ('STRAP', "Strap", "Narrow flexible strip or accessory"),
    ]

GARMENT_FABRIC_ITEMS = [
    ('COTTON', "Cotton", "Balanced fabric for general preview"),
    ('DENIM', "Denim", "Heavy and stiff fabric"),
    ('LEATHER', "Leather", "Dense fabric with high damping"),
    ('SILK', "Silk", "Light and flexible fabric"),
    ('NYLON', "Nylon", "Light synthetic fabric"),
    ('RUBBER', "Rubber", "Heavy elastic material"),
    ('CUSTOM', "Custom", "Use explicit numeric settings"),
    ]

GARMENT_QUALITY_ITEMS = [
    ('DRAFT', "Draft", "Fast low-quality simulation"),
    ('PREVIEW', "Preview", "Balanced interactive simulation"),
    ('FINAL', "Final", "Higher quality settling pass"),
    ]

GARMENT_STATE_ITEMS = [
    ('DRAFT', "Draft", "Editable garment setup"),
    ('READY', "Ready", "Validated and ready to simulate"),
    ('SIMULATING', "Simulating", "Live simulation is running"),
    ('PAUSED', "Paused", "Simulation is paused"),
    ('BAKED', "Baked", "Simulation result has been baked"),
    ('ERROR', "Error", "Validation or build failed"),
    ]

GARMENT_BAKE_ITEMS = [
    ('SHAPE_KEY', "Shape Key", "Bake the current simulated pose to a shape key"),
    ('DUPLICATE', "Duplicate Mesh", "Create a duplicate mesh containing the simulated pose"),
    ('MESH', "Current Mesh", "Commit the current simulated pose to this mesh"),
    ]

GARMENT_MOTION_CONSTRAINT_SOURCE_ITEMS = [
    ('NONE', "Off", "Do not submit NvCloth motion constraints"),
    ('PIN_GROUP', "Pin Group", "Use the pinning vertex group as soft motion limits"),
    ('MOTION_GROUP', "Motion Group", "Use a dedicated vertex group for soft motion limits"),
    ('ALL', "All Vertices", "Apply the same motion limit to every particle"),
    ]

GARMENT_SEPARATION_CONSTRAINT_SOURCE_ITEMS = [
    ('NONE', "Off", "Do not submit NvCloth separation constraints"),
    ('SEPARATION_GROUP', "Separation Group",
     "Use a vertex group to keep selected particles outside local separation spheres"),
    ]


class CP77_GarmentSeamPairProps(PropertyGroup):
    name: StringProperty(name="Name", default="Seam Pair")
    target_object: PointerProperty(
        name="Target Panel", type=Object, description="Optional second panel mesh for this seam pair"
        )
    source_vertices: StringProperty(name="Source Vertices", default="")
    target_vertices: StringProperty(name="Target Vertices", default="")
    source_count: IntProperty(name="Source Count", default=0, min=0)
    target_count: IntProperty(name="Target Count", default=0, min=0)
    stitch_distance: FloatProperty(name="Stitch Distance", default=0.0, min=0.0, max=10.0)
    stitch_strength: FloatProperty(name="Stitch Strength", default=1.0, min=0.0, max=1.0)
    motion_radius: FloatProperty(name="Motion Radius", default=0.05, min=0.0, max=10.0)
    pin_endpoints: BoolProperty(name="Pin Endpoints", default=False)
    use_motion_constraints: BoolProperty(name="Create Motion Group", default=True)
    status: StringProperty(name="Status", default="Not captured")


class CP77_ClothMeshProps(PropertyGroup):
    enabled: BoolProperty(name="Enable Cloth", default=False)
    avatar_armature: PointerProperty(
        name="Avatar", type=Object, description="Avatar armature that provides the garment collision profile"
        )
    workflow_state: EnumProperty(name="State", items=GARMENT_STATE_ITEMS, default='DRAFT')
    garment_type: EnumProperty(name="Garment Type", items=GARMENT_TYPE_ITEMS, default='CUSTOM')
    fabric_preset: EnumProperty(name="Fabric", items=GARMENT_FABRIC_ITEMS, default='COTTON')
    quality_preset: EnumProperty(name="Quality", items=GARMENT_QUALITY_ITEMS, default='PREVIEW')
    pin_vg: StringProperty(name="Pinning Group", default="PINNED_VERTS")
    auto_pin_fallback: BoolProperty(name="Auto Pin Fallback", default=False)
    pin_weight_threshold: FloatProperty(name="Pin Threshold", default=0.5, min=0.0, max=1.0)
    motion_constraint_source: EnumProperty(
        name="Motion Constraints", items=GARMENT_MOTION_CONSTRAINT_SOURCE_ITEMS, default='NONE'
        )
    motion_constraint_vg: StringProperty(name="Motion Group", default="MOTION_LIMIT")
    motion_constraint_radius: FloatProperty(name="Motion Radius", default=0.08, min=0.0, max=10.0)
    motion_constraint_min_radius: FloatProperty(name="Tight Radius", default=0.0, min=0.0, max=10.0)
    motion_constraint_scale: FloatProperty(name="Motion Scale", default=1.0, min=0.0, max=10.0)
    motion_constraint_bias: FloatProperty(name="Motion Bias", default=0.0, min=-10.0, max=10.0)
    motion_constraint_stiffness: FloatProperty(name="Motion Stiffness", default=0.85, min=0.0, max=1.0)
    separation_constraint_source: EnumProperty(
        name="Separation Constraints", items=GARMENT_SEPARATION_CONSTRAINT_SOURCE_ITEMS, default='NONE'
        )
    separation_constraint_vg: StringProperty(name="Separation Group", default="SEPARATION")
    separation_constraint_radius: FloatProperty(name="Separation Radius", default=0.05, min=0.0, max=10.0)
    separation_constraint_offset: FloatProperty(name="Separation Offset", default=0.0, min=-10.0, max=10.0)
    collision_inflate: FloatProperty(name="Collider Inflate", default=0.0, min=0.0, max=1.0)
    continuous_collision: BoolProperty(name="Continuous Collision", default=True)
    collision_mass_scale: FloatProperty(name="Collision Mass Scale", default=3.0, min=0.0, max=50.0)
    mass: FloatProperty(name="Mass", default=1.0, min=0.01)
    drag: FloatProperty(name="Drag", default=0.0, min=0.0)
    friction: FloatProperty(name="Friction", default=0.5, min=0.0, max=1.0)
    damping: FloatProperty(name="Damping", default=0.12, min=0.0, max=10.0)
    linear_drag: FloatProperty(name="Linear Drag", default=0.05, min=0.0, max=10.0)
    solver_frequency: FloatProperty(name="Solver Hz", default=300.0, min=30.0, max=2000.0)
    stiffness_frequency: FloatProperty(name="Stiffness Hz", default=120.0, min=1.0, max=1000.0)
    tether_scale: FloatProperty(name="Tether Scale", default=1.0, min=0.0, max=10.0)
    tether_stiffness: FloatProperty(name="Tether Stiffness", default=1.0, min=0.0, max=10.0)
    self_collision_distance: FloatProperty(name="Self Collision", default=0.004, min=0.0, max=1.0)
    self_collision_stiffness: FloatProperty(name="Self Collision Stiffness", default=0.5, min=0.0, max=1.0)
    bake_target: EnumProperty(name="Bake Target", items=GARMENT_BAKE_ITEMS, default='SHAPE_KEY')
    bake_shape_key: StringProperty(name="Shape Key", default="Cloth Sim")
    validation_status: StringProperty(name="Validation", default="Not prepared")
    validation_errors: StringProperty(name="Validation Errors", default="")
    last_particle_count: IntProperty(name="Particles", default=0, min=0)
    last_triangle_count: IntProperty(name="Triangles", default=0, min=0)
    last_pinned_count: IntProperty(name="Pinned", default=0, min=0)
    last_motion_constraint_count: IntProperty(name="Motion Constraints", default=0, min=0)
    last_separation_constraint_count: IntProperty(name="Separation Constraints", default=0, min=0)
    last_collider_count: IntProperty(name="Colliders", default=0, min=0)


registration_classes = get_classes(sys.modules[__name__])


=======
>>>>>>> Stashed changes
_LEDGER = RegistrationLedger("cyber_props")


def register_props():
    if _LEDGER.active:
        return
    try:
        _LEDGER.register_classes(registration_classes)
        _LEDGER.add_property(
<<<<<<< Updated upstream
            bpy.types.Scene,
            "cp77_facial",
            bpy.props.PointerProperty(type=CP77_FacialProps),
        )
        _LEDGER.add_property(
=======
>>>>>>> Stashed changes
            Scene,
            "cp77_panel_props",
            PointerProperty(type=CP77_PT_PanelProps),
        )
<<<<<<< Updated upstream
        _LEDGER.add_property(
            Scene,
            "rm_data",
            PointerProperty(type=RootMotionData),
        )
        object_properties = {
            "cp77_cloth_colliders": CollectionProperty(type=CP77_ClothColliderProps),
            "cp77_cloth_collider_index": IntProperty(),
            "cp77_avatar": PointerProperty(type=CP77_AvatarProfileProps),
            "cp77_avatar_anchors": CollectionProperty(type=CP77_AvatarAnchorProps),
            "cp77_avatar_anchor_index": IntProperty(),
            "cp77_cloth": PointerProperty(type=CP77_ClothMeshProps),
            "cp77_garment_seams": CollectionProperty(type=CP77_GarmentSeamPairProps),
            "cp77_garment_seam_index": IntProperty(),
            "cp77_cloth_handle": StringProperty(default="-1"),
        }
        for name, value in object_properties.items():
            _LEDGER.add_property(bpy.types.Object, name, value)
        update_presets_items()
=======
>>>>>>> Stashed changes
    except Exception:
        _LEDGER.cleanup()
        raise


def unregister_props():
<<<<<<< Updated upstream
    failures = _LEDGER.cleanup()
    if failures:
        raise RuntimeError("; ".join(f"{label}: {error}" for label, error in failures))
=======
    _LEDGER.cleanup_or_raise()
>>>>>>> Stashed changes
