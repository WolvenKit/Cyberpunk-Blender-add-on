import math
import time

import bpy
from bpy.props import (
    BoolProperty,
    CollectionProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    IntProperty,
    PointerProperty,
    StringProperty,
)

from ..bartmoss.vehicle import STANDARD_GRAVITY
from ..blender.physics.objects import update_collision_bits
from ..core.log import debug_exception, get_logger, log_once
from ..core.notifications import report
from ..physics.model.collision_layers import DEFAULT_PRESET_INDEX, get_preset_items
from ..physics.model.materials import physics_material_enum_items
from .runtime.dangle.rigs import clear_dangle_rigs
from .services.scene import update_gravity
from .services.vehicle_resolver import base_vehicle_choices, record_override_choices

_LOG = get_logger(__name__)

ENUM_SOLVER_TYPE = [
    ("DYNG", "Dyng (Particles)", "Particle-based dynamic bone simulation"),
    ("PENDULUM", "Pendulum", "Simple pendulum per bone"),
    ("SPRING", "Spring", "Spring-mass per bone"),
    ("PBD", "Position Projection", "Single-bone collision position projection"),
]

ENUM_DYNG_LINK_TYPE = [
    ("FIXED", "KeepFixedDistance", "Enforce exact rest length ratio"),
    ("VARIABLE", "KeepVariableDistance", "Clamp within ratio bounds"),
    ("GREATER", "Greater", "Enforce minimum distance"),
    ("CLOSER", "Closer", "Enforce maximum distance"),
]

ENUM_DYNG_PARTICLE_PROJECTION_TYPE = [
    ("DISABLED", "Disabled", "No projection"),
    ("SHORTEST_PATH", "ShortestPath", "Project to nearest surface radially"),
    ("DIRECTED", "Directed", "Project strictly along capsule axis"),
]

ENUM_POSITION_PROJECTION_TYPE = [
    ("DISABLED", "Disabled", "No projection"),
    ("SHORTEST_PATH", "ShortestPath", "Project to nearest surface radially"),
    ("DIRECTIONAL", "Directional", "Project along directional reference axis"),
]

ENUM_SPRING_PROJECTION_TYPE = [
    ("DISABLED", "Disabled", "No collision projection"),
    (
        "SHORTEST_PATH",
        "ShortestPath",
        "Project the spring collision sphere to the nearest surface",
    ),
]

ENUM_PENDULUM_CONSTRAINT_TYPE = [
    ("CONE", "Cone", "Constrain within a circular aperture"),
    ("HINGE_PLANE", "HingePlane", "Constrain strictly to a 2D disk slice"),
    ("HALF_CONE", "HalfCone", "Constrain to a 180-degree hemispherical cone"),
]

ENUM_PENDULUM_PROJECTION_TYPE = [
    ("DISABLED", "Disabled", "No projection"),
    (
        "SHORTEST_PATH_ROTATIONAL",
        "ShortestPathRotational",
        "Rotational projection to nearest surface",
    ),
    (
        "DIRECTED_ROTATIONAL",
        "DirectedRotational",
        "Rotational projection along directed axis",
    ),
]


def _dangle_rig_changed(_self, _context):
    clear_dangle_rigs()


def _active_chain_update(self, context):
    from .services.dangles.selection import on_active_chain_update

    on_active_chain_update(self, context)


def _active_particle_update(self, context):
    from .services.dangles.selection import on_active_particle_update

    on_active_particle_update(self, context)


ENUM_COLLISION_SHAPE_TYPE = [
    ("SPHERE", "Sphere", "Rounded shape with no box extents"),
    ("CAPSULE", "Capsule", "Rounded shape with one non-zero box extent"),
    ("ROUNDED_BOX", "Rounded Box", "Rounded shape with multiple box extents"),
]


class DANGLE_ConstraintLinkConfig(bpy.types.PropertyGroup):
    source_path: StringProperty(options={"HIDDEN"})
    target_bone: StringProperty(name="Target Bone")
    link_type: EnumProperty(
        name="Link Type", items=ENUM_DYNG_LINK_TYPE, default="FIXED"
    )
    lower_ratio: FloatProperty(name="Lower Bound (%)", default=100.0, min=0.0)
    upper_ratio: FloatProperty(name="Upper Bound (%)", default=100.0, min=0.0)

    explicit_rest_distance: FloatProperty(
        name="Rest Distance",
        default=0.0,
        min=0.0,
        description="Cached reference-pose distance (0 = compute from pose)",
    )
    stiffness: FloatProperty(
        name="Stiffness",
        default=1.0,
        min=0.0,
        max=1.0,
        description="Stiffness",
    )

    look_at_axis: FloatVectorProperty(
        name="Look At Axis",
        size=3,
        default=(1.0, 0.0, 0.0),
        description="REDengine bone-local look-at axis",
    )


class DANGLE_ConstraintEllipsoidConfig(bpy.types.PropertyGroup):
    source_path: StringProperty(options={"HIDDEN"})
    target_bone: StringProperty(name="Constrained Bone")
    radius: FloatProperty(name="Radius", default=0.1, min=0.0)
    scale1: FloatProperty(name="Scale 1 (Z-)", default=1.0, min=0.001)
    scale2: FloatProperty(name="Scale 2 (Z+)", default=1.0, min=0.001)

    ellipsoid_transform_ls_quat: FloatVectorProperty(
        name="Ellipsoid Transform LS (wxyz)",
        size=4,
        default=(1.0, 0.0, 0.0, 0.0),
        description="Local-space rotation offset for ellipsoid (quaternion wxyz)",
    )
    ellipsoid_transform_ls_offset: FloatVectorProperty(
        name="Ellipsoid Transform LS Offset",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="Local-space translation offset for ellipsoid",
    )


class DANGLE_ConstraintPendulumConfig(bpy.types.PropertyGroup):
    source_path: StringProperty(options={"HIDDEN"})
    target_bone: StringProperty(name="Attachment Bone")
    constraint_type: EnumProperty(
        name="Shape",
        items=ENUM_PENDULUM_CONSTRAINT_TYPE,
        default="CONE",
    )
    half_aperture_angle: FloatProperty(
        name="Half Aperture Angle",
        default=45.0,
        min=0.0,
        max=180.0,
        description="HALF of maximum angle between generating lines",
    )
    projection_type: EnumProperty(
        name="Projection",
        items=ENUM_PENDULUM_PROJECTION_TYPE,
        default="DISABLED",
    )

    cone_collision_radius: FloatProperty(
        name="Cone Capsule Radius",
        default=0.0,
        min=0.0,
        description="Radius of the cone constraint's collision capsule",
    )
    cone_collision_height: FloatProperty(
        name="Cone Capsule Height Extent",
        default=0.0,
        min=0.0,
        description="Height extent of the cone constraint's collision capsule",
    )

    cone_transform_ls_quat: FloatVectorProperty(
        name="Cone Transform LS (wxyz)",
        size=4,
        default=(1.0, 0.0, 0.0, 0.0),
        description="REDengine local-space rotation for the cone shape",
    )
    cone_transform_ls_offset: FloatVectorProperty(
        name="Cone Transform LS Offset",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="REDengine local-space translation for the cone shape",
    )


class DANGLE_ConstraintOrderEntry(bpy.types.PropertyGroup):
    constraint_type: EnumProperty(
        name="Constraint Type",
        items=[
            ("LINK", "Link", "Distance link constraint"),
            ("ELLIPSOID", "Ellipsoid", "Ellipsoid constraint"),
            ("CONE", "Cone", "Cone/pendulum constraint"),
        ],
    )
    particle_bone: StringProperty(name="Particle Bone")
    constraint_index: IntProperty(name="Constraint Index", default=0, min=0)


class DANGLE_CollisionShape(bpy.types.PropertyGroup):
    source_index: IntProperty(default=-1, min=-1, options={"HIDDEN"})
    name: StringProperty(name="Shape Name", default="Shape")
    bone_name: StringProperty(name="Attached Bone")
    shape_type: EnumProperty(
        name="Type", items=ENUM_COLLISION_SHAPE_TYPE, default="SPHERE"
    )
    radius: FloatProperty(name="Radius", default=0.05, min=0.0)
    height_extent: FloatProperty(
        name="Z Box Extent",
        default=0.1,
        min=0.0,
        description="Box half-extent along Z axis (most common capsule axis)",
    )
    x_box_extent: FloatProperty(
        name="X Box Extent",
        default=0.0,
        min=0.0,
        description="Box half-extent along X axis",
    )
    y_box_extent: FloatProperty(
        name="Y Box Extent",
        default=0.0,
        min=0.0,
        description="Box half-extent along Y axis",
    )
    offset_ls: FloatVectorProperty(name="Offset (LS)", size=3, default=(0.0, 0.0, 0.0))
    rotation_ls_quat: FloatVectorProperty(
        name="Rotation LS (wxyz)",
        size=4,
        default=(1.0, 0.0, 0.0, 0.0),
        description="Local-space rotation for collision shape (quaternion wxyz)",
    )


class DANGLE_Particle(bpy.types.PropertyGroup):
    source_index: IntProperty(default=-1, min=-1, options={"HIDDEN"})
    bone_name: StringProperty(name="Bone")

    mass: FloatProperty(name="Mass", default=1.0, min=0.001)
    damping: FloatProperty(name="Damping", default=1.0, min=0.0)
    pull_force: FloatProperty(name="Pull Force Factor", default=0.0, min=0.0)
    is_pinned: BoolProperty(
        name="Pinned (Skip Physics)",
        default=False,
        description="When set, particle follows animation, not simulation",
    )

    capsule_radius: FloatProperty(name="Capsule Radius", default=0.0, min=0.0)
    capsule_height: FloatProperty(name="Capsule Height Extent", default=0.0, min=0.0)
    capsule_axis_ls: FloatVectorProperty(
        name="Capsule Axis (LS)",
        size=3,
        default=(0.5, 0.0, 0.0),
        description="REDengine bone-local capsule axis",
    )
    dyng_projection_type: EnumProperty(
        name="Dyng Projection",
        items=ENUM_DYNG_PARTICLE_PROJECTION_TYPE,
        default="SHORTEST_PATH",
    )
    pos_projection_type: EnumProperty(
        name="Pos Projection",
        items=ENUM_POSITION_PROJECTION_TYPE,
        default="SHORTEST_PATH",
    )
    direction_reference_bone: StringProperty(name="Direction Reference Bone")

    spring_simulation_fps: FloatProperty(
        name="Simulation FPS",
        default=10.0,
        min=10.0,
        description="Internal fixed-step rate used by the standalone Spring solver",
    )
    spring_constraint_radius: FloatProperty(
        name="Constraint Radius",
        default=0.5,
        min=0.0,
        description="Base radius of the two-sided ellipsoid surrounding the spring",
    )
    spring_constraint_scale1: FloatProperty(
        name="Constraint Scale 1 (Z-)",
        default=1.0,
        min=0.01,
    )
    spring_constraint_scale2: FloatProperty(
        name="Constraint Scale 2 (Z+)",
        default=1.0,
        min=0.01,
    )
    spring_constraint_orientation: FloatVectorProperty(
        name="Constraint Orientation",
        size=2,
        default=(0.0, 90.0),
        description="REDengine X/Y rotation angles for the constraint ellipsoid",
    )
    spring_pull_force_origin_ls: FloatVectorProperty(
        name="Pull Force Origin (LS)",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="REDengine parent-bone-local attraction point",
    )
    spring_projection_type: EnumProperty(
        name="Spring Projection",
        items=ENUM_SPRING_PROJECTION_TYPE,
        default="SHORTEST_PATH",
    )
    spring_collision_radius: FloatProperty(
        name="Collision Sphere Radius",
        default=0.0,
        min=0.0,
    )

    pendulum_simulation_fps: FloatProperty(
        name="Simulation FPS",
        default=10.0,
        min=10.0,
    )
    pendulum_constraint_type: EnumProperty(
        name="Constraint Shape",
        items=ENUM_PENDULUM_CONSTRAINT_TYPE,
        default="CONE",
    )
    pendulum_half_aperture_angle: FloatProperty(
        name="Half Aperture Angle",
        default=45.0,
        min=0.0,
        max=180.0,
    )
    pendulum_constraint_orientation: FloatVectorProperty(
        name="Constraint Orientation",
        size=3,
        default=(90.0, 0.0, 0.0),
        description="REDengine X/Y/Z orientation angles for the pendulum constraint",
    )
    pendulum_pull_force_direction_ls: FloatVectorProperty(
        name="Pull Force Direction (LS)",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="REDengine parent-bone-local constant pull direction",
    )
    pendulum_projection_type: EnumProperty(
        name="Projection",
        items=ENUM_PENDULUM_PROJECTION_TYPE,
        default="SHORTEST_PATH_ROTATIONAL",
    )
    pendulum_collision_radius: FloatProperty(
        name="Collision Capsule Radius",
        default=0.0,
        min=0.0,
    )
    pendulum_collision_height: FloatProperty(
        name="Collision Capsule Height Extent",
        default=0.0,
        min=0.0,
    )

    link_constraints: CollectionProperty(type=DANGLE_ConstraintLinkConfig)
    ellipsoid_constraints: CollectionProperty(type=DANGLE_ConstraintEllipsoidConfig)
    pendulum_constraints: CollectionProperty(type=DANGLE_ConstraintPendulumConfig)


class DANGLE_DragNode(bpy.types.PropertyGroup):
    source_handle: StringProperty(name="Source Handle", options={"HIDDEN"})
    source_bone_name: StringProperty(
        name="Source Bone",
        description="Bone used to initialize the source point",
    )
    bone_name: StringProperty(
        name="Bone",
        description="The bone to apply drag to",
    )
    simulation_fps: FloatProperty(
        name="Simulation FPS",
        default=100.0,
        min=1.0,
        max=240.0,
        description="Internal simulation rate for the drag integrator",
    )
    source_speed_multiplier: FloatProperty(
        name="Speed Multiplier",
        default=10.0,
        min=0.0,
        description="Catch-up rate — higher = faster convergence, less visible lag",
    )
    has_overshoot: BoolProperty(
        name="Has Overshoot",
        default=True,
        description="Enable velocity overshoot detection",
    )
    overshoot_detection_min_speed: FloatProperty(
        name="Overshoot Min Speed",
        default=0.4,
        min=0.0,
    )
    overshoot_detection_max_speed: FloatProperty(
        name="Overshoot Max Speed",
        default=4.0,
        min=0.0,
    )
    overshoot_duration: FloatProperty(
        name="Overshoot Duration",
        default=1.0,
        min=0.0,
    )

    use_steps: BoolProperty(
        name="Use Steps",
        default=False,
        description="When active, target moves in discrete steps",
    )
    steps_target_speed_multiplier: FloatProperty(
        name="Steps Speed Multiplier",
        default=10000.0,
        min=0.0,
        description="Speed of target point when step movement is active",
    )
    time_between_steps: FloatProperty(
        name="Time Between Steps",
        default=0.1,
        min=0.001,
        description="Duration of interval between steps (target follows bone)",
    )
    time_in_step: FloatProperty(
        name="Time In Step",
        default=0.1,
        min=0.001,
        description="Duration of step (target frozen)",
    )


class DANGLE_Chain(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Chain")
    solver: EnumProperty(name="Solver", items=ENUM_SOLVER_TYPE, default="DYNG")

    particles: CollectionProperty(type=DANGLE_Particle)
    active_particle_index: IntProperty(
        name="Active Particle",
        default=0,
        update=_active_particle_update,
    )


class DANGLE_DangleNode(bpy.types.PropertyGroup):
    source_identity_version: IntProperty(default=0, options={"HIDDEN"})
    constraint_source_paths: StringProperty(default="[]", options={"HIDDEN"})
    particle_source_indices: StringProperty(default="[]", options={"HIDDEN"})
    import_warnings: StringProperty(options={"HIDDEN"})
    external_force_linked: BoolProperty(default=False, options={"HIDDEN"})
    external_force_preview_error: StringProperty(options={"HIDDEN"})
    source_handle: StringProperty(name="Source Handle", options={"HIDDEN"})
    name: StringProperty(name="Name", default="DangleNode")

    alpha: FloatProperty(
        name="Alpha Blend Weight",
        default=1.0,
        min=0.0,
        max=1.0,
    )
    rotate_parent_to_look_at: BoolProperty(
        name="Rotate Parent to Look At",
        default=True,
    )
    look_at_axis: FloatVectorProperty(
        name="Look At Axis",
        size=3,
        default=(1.0, 0.0, 0.0),
        description="REDengine bone-local look-at axis",
    )
    gravity_ws: FloatProperty(
        name="Gravity (WS)",
        default=STANDARD_GRAVITY,
        description="Signed world-space gravity value authored for this node",
    )
    external_force_ws: FloatVectorProperty(
        name="External Force (WS)",
        size=3,
        default=(0.0, 0.0, 0.0),
    )
    parent_rotation_alters_dangle_children: BoolProperty(
        name="Turn Dangle Children",
        description="The parent's rotation turns its dangle children (parentRotationAltersDangleChildren)",
        default=True,
    )
    parent_rotation_alters_non_dangle_children: BoolProperty(
        name="Turn Other Children",
        description="The parent's rotation turns its other children (parentRotationAltersNonDangleChildren)",
        default=True,
    )
    dangle_alters_children: BoolProperty(
        name="Dangle Alters Children",
        default=True,
    )

    substep_time: FloatProperty(
        name="Substep Time",
        default=0.01,
        min=0.005,
        max=0.1,
        description="Seconds per physics substep for this node",
    )
    solver_iterations: IntProperty(
        name="Solver Iterations",
        default=1,
        min=1,
        max=8,
        description="Constraint solver iteration count",
    )
    imported_solver_iterations: IntProperty(
        name="Imported Solver Iterations",
        default=0,
        min=0,
        description="Original solver iterations",
    )

    chains: CollectionProperty(type=DANGLE_Chain)
    active_chain: IntProperty(
        name="Active Chain",
        default=0,
        update=_active_chain_update,
    )

    constraint_order: CollectionProperty(type=DANGLE_ConstraintOrderEntry)

    collision_shapes: CollectionProperty(type=DANGLE_CollisionShape)
    active_shape_index: IntProperty(name="Active Node Shape", default=0)


class DANGLE_PreviewVectorInput(bpy.types.PropertyGroup):
    key: StringProperty(options={"HIDDEN"})
    group: StringProperty(name="Group", options={"HIDDEN"})
    input_name: StringProperty(name="Input", options={"HIDDEN"})
    source_handle: StringProperty(name="Source Handle", options={"HIDDEN"})
    value: FloatVectorProperty(
        name="Value",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="Preview-only live VectorInput value; exported AnimGraph data is unchanged",
    )


class DANGLE_PreviewVisualTag(bpy.types.PropertyGroup):
    tag: StringProperty(name="Visual Tag")
    graph_path: StringProperty(name="Graph Path", options={"HIDDEN"})


class DANGLE_GraphOperation(bpy.types.PropertyGroup):
    node_type: EnumProperty(
        name="Node Type",
        items=[
            ("DANGLE", "Dangle", "animAnimNode_Dangle operation"),
            ("DRAG", "Drag", "animAnimNode_Drag operation"),
        ],
        default="DANGLE",
    )
    node_index: IntProperty(name="Node Index", default=0, min=0)
    source_handle: StringProperty(name="Source Handle")
    graph_path: StringProperty(name="Graph Path")


class DANGLE_AddonState(bpy.types.PropertyGroup):
    preview_mode: EnumProperty(
        name="Preview",
        items=[
            ("GRAPH", "Graph", "Evaluate supported linear graph operations"),
            (
                "SELECTED",
                "Selected Dangle",
                "Simulate only the selected Dangle using the current Blender pose; graph constraints, switches, blends and Drag nodes are excluded",
            ),
        ],
        default="GRAPH",
    )
    preview_visual_tags: StringProperty(
        name="Preview Visual Tags",
        description="Comma-separated visual tags for graph preview; blank means an empty tag set. Applied when Play is pressed; does not change the exported graph",
    )
    preview_component_tags: StringProperty(
        name="Preview Component Tags",
        description="Comma-separated animation component tags for graph preview (ComponentTagCondition); blank means an untagged component. Applied when Play is pressed; does not change the exported graph",
    )
    preview_skeletal_lod: IntProperty(
        name="Skeletal LOD",
        default=0,
        min=0,
        max=15,
        description="REDengine animation level of detail used to resolve ConditionalSegment branches during Graph preview; 0 is highest quality",
    )
    preview_performance_mode: BoolProperty(
        name="Performance Mode",
        default=False,
        description="Resolve SkipPerformanceMode segments as skipped during Graph preview; preview-only and not exported",
    )
    preview_external_events: StringProperty(
        name="External Events",
        description="Comma-separated external AnimGraph events fired once on the next Graph preview update; consumed after firing and not exported",
    )
    preview_anim_features_json: StringProperty(
        name="Anim Features",
        default="{}",
        description='Preview-only feature values as JSON, for example {"seat_front_left_window":{"state":1}}; not exported',
    )
    preview_look_at_parts: StringProperty(options={"HIDDEN"})
    preview_look_at_enabled: BoolProperty(name="Look at Target", default=False)
    preview_look_at_part: StringProperty(name="Body Part", default="Eyes")
    preview_look_at_object: PointerProperty(
        name="Target Object",
        type=bpy.types.Object,
        description="Follow this object's world position during graph preview",
    )
    preview_look_at_target: FloatVectorProperty(
        name="Target Position",
        size=3,
        default=(0.0, 3.0, 1.6),
        subtype="TRANSLATION",
        description="Target position in the rig's model space when no target object is selected",
    )
    preview_look_at_speed: FloatProperty(
        name="Transition Speed",
        default=60.0,
        min=0.01,
        description="Angular speed in degrees per second when acquiring or releasing the target",
    )
    preview_force_ws: FloatVectorProperty(
        name="Preview Force (WS)",
        size=3,
        default=(0.0, 0.0, 0.0),
        description="External force for Selected Dangle preview, replacing the graph force input; exported settings are unchanged",
    )
    preview_vector_inputs: CollectionProperty(type=DANGLE_PreviewVectorInput)
    preview_visual_tag_requirements: CollectionProperty(type=DANGLE_PreviewVisualTag)
    graph_compiled: BoolProperty(default=False, options={"HIDDEN"})
    evaluation_boundary: StringProperty(name="Preview Boundary", options={"HIDDEN"})
    preview_input_error: StringProperty(name="Preview Input Error", options={"HIDDEN"})
    is_dangle_rig: BoolProperty(
        name="Is Dangle Rig", default=False, update=_dangle_rig_changed
    )
    is_playing: BoolProperty(name="Preview Playing", default=False)

    animgraph_source_text: StringProperty(
        name="AnimGraph Source Text",
        description="Hidden Text datablock containing the complete imported WolvenKit document",
    )
    animgraph_source_path: StringProperty(
        name="AnimGraph Source Path",
        subtype="FILE_PATH",
    )
    animgraph_tree_name: StringProperty(
        name="Full AnimGraph Tree",
        description="REDengine AnimGraph node tree synchronized with this specialist editor",
    )
    animgraph_last_export_path: StringProperty(
        name="Last AnimGraph Export",
        subtype="FILE_PATH",
    )

    external_force_ws: FloatVectorProperty(
        name="External Force (WS)",
        size=3,
        default=(0.0, 0.0, 0.0),
    )

    substep_time: FloatProperty(
        name="Substep Time",
        default=0.01,
        min=0.005,
        max=0.1,
        description="Global seconds per physics substep",
    )
    substeps: IntProperty(
        name="Substeps (legacy)",
        default=1,
        min=1,
        max=10,
        description="Legacy substep count",
    )
    solver_iterations: IntProperty(
        name="Solver Iterations",
        default=1,
        min=1,
        max=8,
        description="Legacy global solver iteration count",
    )
    imported_solver_iterations: IntProperty(
        name="Imported Solver Iterations",
        default=0,
        min=0,
        description="Original solver iterations",
    )

    collision_shapes: CollectionProperty(type=DANGLE_CollisionShape)
    active_shape_index: IntProperty(name="Active Shape", default=0)

    dangle_nodes: CollectionProperty(type=DANGLE_DangleNode)
    active_dangle_node: IntProperty(name="Active Dangle Node", default=0)

    drag_nodes: CollectionProperty(type=DANGLE_DragNode)

    evaluation_order: CollectionProperty(type=DANGLE_GraphOperation)

    show_global_body_shapes: BoolProperty(
        name="Body Collision Shapes",
        default=True,
        description="Master toggle for body collision shape overlays",
    )
    show_global_capsules: BoolProperty(
        name="Particle Capsules",
        default=True,
        description="Master toggle for particle collision capsule overlays",
    )
    show_global_constraints: BoolProperty(
        name="Link Constraints",
        default=True,
        description="Master toggle for distance link overlays",
    )
    show_global_cones: BoolProperty(
        name="Cone Constraints",
        default=True,
        description="Master toggle for cone/pendulum constraint overlays",
    )
    show_global_velocity: BoolProperty(
        name="Velocity Vectors",
        default=False,
        description="Master toggle for velocity debug vectors",
    )


DANGLE_PROPERTY_CLASSES = (
    DANGLE_ConstraintLinkConfig,
    DANGLE_ConstraintEllipsoidConfig,
    DANGLE_ConstraintPendulumConfig,
    DANGLE_ConstraintOrderEntry,
    DANGLE_CollisionShape,
    DANGLE_Particle,
    DANGLE_DragNode,
    DANGLE_Chain,
    DANGLE_DangleNode,
    DANGLE_PreviewVectorInput,
    DANGLE_PreviewVisualTag,
    DANGLE_GraphOperation,
    DANGLE_AddonState,
)

_ENUM_CACHE_TTL = 1.0
_ARMATURE_ITEMS_CACHE = {"expires": 0.0, "object_count": -1, "items": ()}
_BONE_ITEMS_CACHE = {}


def update_physics_material(self, context):
    value = str(self.physics_material or "Default")
    self.physics_material_source = value
    self.physics_material_storage = "string"


def clear_property_item_caches():
    _ARMATURE_ITEMS_CACHE["expires"] = 0.0
    _ARMATURE_ITEMS_CACHE["object_count"] = -1
    _ARMATURE_ITEMS_CACHE["items"] = ()
    _BONE_ITEMS_CACHE.clear()


def update_gravity_cb(self, context):
    if self.is_initialized:
        result = update_gravity(context)
        if not result.ok:
            self.is_initialized = False
            report(None, "WARNING", result.message, error=result.error, logger=_LOG)


def get_armature_items(self, context):
    object_count = len(context.scene.objects)
    now = time.monotonic()
    cache = _ARMATURE_ITEMS_CACHE
    if cache["object_count"] == object_count and now < cache["expires"]:
        return cache["items"]
    items = [("NONE", "None", "No armature selected")]
    items.extend(
        (obj.name, obj.name, f"Armature: {obj.name}")
        for obj in context.scene.objects
        if obj.type == "ARMATURE"
    )
    cache["object_count"] = object_count
    cache["expires"] = now + _ENUM_CACHE_TTL
    cache["items"] = tuple(items)
    return cache["items"]


def update_parent_armature(self, context):
    self.target_bone = "NONE"


def get_bone_items(self, context):
    items = [("NONE", "None", "No bone selected")]
    if not self.parent_armature or self.parent_armature == "NONE":
        return items
    armature_obj = context.scene.objects.get(self.parent_armature)
    if armature_obj is None or armature_obj.type != "ARMATURE":
        return items
    try:
        pointer = int(armature_obj.data.as_pointer())
    except (AttributeError, ReferenceError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("get_bone_items", type(error).__name__),
            "get bone items: fell back after %s",
            error,
            exc_info=True,
        )
        pointer = 0
    key = armature_obj.name
    bone_count = len(armature_obj.data.bones)
    now = time.monotonic()
    cached = _BONE_ITEMS_CACHE.get(key)
    if cached and cached[0] == pointer and cached[1] == bone_count and now < cached[2]:
        return cached[3]
    items.extend(
        (bone.name, bone.name, f"Bone: {bone.name}") for bone in armature_obj.data.bones
    )
    result = tuple(items)
    _BONE_ITEMS_CACHE[key] = (pointer, bone_count, now + _ENUM_CACHE_TTL, result)
    return result


class PhysXShapeItem(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(default="Shape")
    shape_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ("BOX", "Box", ""),
            ("SPHERE", "Sphere", ""),
            ("CAPSULE", "Capsule", ""),
            ("CONVEX", "Convex", ""),
            ("TRIANGLE", "Triangle", ""),
            ("HEIGHTFIELD", "HeightField", ""),
        ],
        default="BOX",
    )
    # Source shapes can be thinner than a centimetre, so only dragging stops there.
    dim_x: bpy.props.FloatProperty(name="X", default=1.0, min=1e-6, soft_min=0.01)
    dim_y: bpy.props.FloatProperty(name="Y", default=1.0, min=1e-6, soft_min=0.01)
    dim_z: bpy.props.FloatProperty(name="Z", default=1.0, min=1e-6, soft_min=0.01)
    heightfield_rows: bpy.props.IntProperty(name="Rows", default=257, min=2, max=2048)
    heightfield_columns: bpy.props.IntProperty(
        name="Columns", default=257, min=2, max=2048
    )
    heightfield_height_scale: bpy.props.FloatProperty(
        name="Height Scale", default=1.0, min=1.0e-9
    )
    heightfield_row_scale: bpy.props.FloatProperty(
        name="Row Scale", default=1.0, min=1.0e-9
    )
    heightfield_column_scale: bpy.props.FloatProperty(
        name="Column Scale", default=1.0, min=1.0e-9
    )
    heightfield_extents: bpy.props.FloatVectorProperty(
        name="Extents", size=3, default=(1.0, 1.0, 1.0), min=0.0, options={"HIDDEN"}
    )
    heightfield_materials_json: bpy.props.StringProperty(default="", options={"HIDDEN"})
    heightfield_material_indices_json: bpy.props.StringProperty(
        default="", options={"HIDDEN"}
    )
    heightfield_source_prefab_hash: bpy.props.StringProperty(
        default="0", options={"HIDDEN"}
    )
    local_pos: bpy.props.FloatVectorProperty(name="Position", subtype="TRANSLATION")
    local_rot: bpy.props.FloatVectorProperty(
        name="Orientation",
        subtype="QUATERNION",
        size=4,
        default=(1.0, 0.0, 0.0, 0.0),
    )
    physics_material: bpy.props.EnumProperty(
        items=physics_material_enum_items(),
        name="Material",
        default="Default",
        update=update_physics_material,
    )
    physics_material_source: bpy.props.StringProperty(default="", options={"HIDDEN"})
    physics_material_storage: bpy.props.StringProperty(
        default="string", options={"HIDDEN"}
    )
    cooked_data: bpy.props.StringProperty()
    is_cooked: bpy.props.BoolProperty(default=False)
    vertex_limit: bpy.props.IntProperty(name="Hull Verts", default=64, min=8, max=256)

    collision_preset: bpy.props.EnumProperty(
        name="Collision Preset",
        items=get_preset_items,
        default=DEFAULT_PRESET_INDEX,
        update=update_collision_bits,
    )

    filter_group: bpy.props.BoolVectorProperty(size=20, subtype="LAYER_MEMBER")
    filter_mask: bpy.props.BoolVectorProperty(size=20, subtype="LAYER_MEMBER")
    filter_query: bpy.props.BoolVectorProperty(size=20, subtype="LAYER_MEMBER")
    filter_source_preset: bpy.props.StringProperty(default="", options={"HIDDEN"})
    filter_source_sim_group: bpy.props.StringProperty(default="", options={"HIDDEN"})
    filter_source_sim_target: bpy.props.StringProperty(default="", options={"HIDDEN"})
    filter_source_query_mask: bpy.props.StringProperty(default="", options={"HIDDEN"})
    filter_source_signature: bpy.props.StringProperty(default="", options={"HIDDEN"})
    source_phys_shape_metadata_json: bpy.props.StringProperty(
        default="", options={"HIDDEN"}
    )


class PhysXActorItem(bpy.types.PropertyGroup):
    obj_ref: bpy.props.PointerProperty(type=bpy.types.Object)
    actor_handle: bpy.props.StringProperty(default="0", options={"SKIP_SAVE"})
    visualization_enabled: bpy.props.BoolProperty(
        name="Visualize",
        description="Draw this actor's PhysX shapes in the collider overlay",
        default=True,
    )

    use_bone_parent: bpy.props.BoolProperty(
        name="Use Bone Parent",
        description="Attach this actor to an armature bone instead of object origin",
        default=False,
    )
    parent_armature: bpy.props.EnumProperty(
        name="Parent Armature",
        description="Select armature object containing the target bone",
        items=get_armature_items,
        update=update_parent_armature,
    )
    target_bone: bpy.props.EnumProperty(
        name="Target Bone",
        description="Select bone within parent armature (bone head is attachment point)",
        items=get_bone_items,
    )

    def poll_armature_availability(self):
        obj = self.obj_ref
        if not obj:
            return False

        if obj.type == "ARMATURE":
            return True

        if obj.parent and obj.parent.type == "ARMATURE":
            return True

        for mod in obj.modifiers:
            if mod.type == "ARMATURE":
                return True

        for const in obj.constraints:
            if (
                const.type in {"CHILD_OF", "ARMATURE"}
                and const.target
                and const.target.type == "ARMATURE"
            ):
                return True

        return False


class PhysXObjectProperties(bpy.types.PropertyGroup):
    actor_type: bpy.props.EnumProperty(
        name="Type",
        items=[
            ("NONE", "Ignored", ""),
            ("STATIC", "Static", ""),
            ("DYNAMIC", "Dynamic", ""),
            ("KINEMATIC", "Kinematic", ""),
        ],
        default="STATIC",
    )
    shapes: bpy.props.CollectionProperty(type=PhysXShapeItem)
    shape_index: bpy.props.IntProperty()
    mass: bpy.props.FloatProperty(name="Mass", default=10.0, min=0.001)
    com_offset: bpy.props.FloatVectorProperty(name="CoM Offset", subtype="TRANSLATION")
    inertia: bpy.props.FloatVectorProperty(name="Inertia", description="Custom inertia")

    calc_mass: bpy.props.BoolProperty(name="Mass", default=True)
    calc_inertia: bpy.props.BoolProperty(name="Inertia", default=True)
    calc_offset: bpy.props.BoolProperty(name="Offset", default=True)

    source_kind: bpy.props.StringProperty(default="", options={"HIDDEN"})
    source_sector: bpy.props.StringProperty(default="", options={"HIDDEN"})
    source_node_data_index: bpy.props.IntProperty(default=-1, options={"HIDDEN"})
    source_actor_index: bpy.props.IntProperty(default=-1, options={"HIDDEN"})
    source_phys_body_metadata_json: bpy.props.StringProperty(
        default="", options={"HIDDEN"}
    )
    source_phys_resource_path: bpy.props.StringProperty(default="", options={"HIDDEN"})


class PhysXSceneProperties(bpy.types.PropertyGroup):
    is_initialized: bpy.props.BoolProperty(default=False)
    ui_tab: bpy.props.EnumProperty(
        items=[
            ("WORLD", "World", "World"),
            ("ACTORS", "Actors", "Actors"),
            ("SIM", "Simulation", "Simulation"),
            ("VEHICLE", "Vehicle", "Vehicle authoring and preview"),
            ("DANGLES", "Dangles", "Dangles"),
        ],
        default="WORLD",
    )
    scene_built: bpy.props.BoolProperty(default=False, name="Scene Built")
    sim_running: bpy.props.BoolProperty(name="Simulating", default=False)
    viz_enabled: bpy.props.BoolProperty(
        name="Debug Draw",
        default=True,
        description="Master toggle for physics and Dangle viewport overlays",
    )

    active_actor_count: bpy.props.IntProperty(default=0)

    actors: bpy.props.CollectionProperty(type=PhysXActorItem)
    actor_list_index: bpy.props.IntProperty()

    gravity: bpy.props.FloatVectorProperty(
        name="Gravity",
        default=(0.0, 0.0, -STANDARD_GRAVITY),
        subtype="ACCELERATION",
        update=update_gravity_cb,
    )

    force_mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ("0", "Force", ""),
            ("1", "Impulse", ""),
            ("2", "Velocity", ""),
            ("3", "Acceleration", ""),
        ],
    )
    force_value: bpy.props.FloatVectorProperty(name="Vector", default=(0, 0, 1000))
    use_force_pos: bpy.props.BoolProperty(name="Use Cursor Pos", default=False)

    sim_steps: bpy.props.IntProperty(name="Steps", default=1, min=1)

    use_grab_mode: bpy.props.BoolProperty(
        name="Enable Manipulator",
        description="Spawn a kinematic sphere to push objects around",
        default=False,
    )
    manipulator_pos: bpy.props.FloatVectorProperty(
        name="Hand Pos", subtype="TRANSLATION"
    )
    manipulator_handle: bpy.props.StringProperty(default="0", options={"SKIP_SAVE"})


def _stale_vehicle_validation(vehicle):
    if getattr(vehicle, "validation_state", "NOT_RUN") != "NOT_RUN":
        vehicle.validation_state = "STALE"


def update_vehicle_authoring(self, context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    physx = getattr(scene, "physx", None)
    if physx is not None:
        physx.scene_built = False
    vehicle = getattr(scene, "physx_vehicle", None) or self
    vehicle.preview_dirty = True
    vehicle.live_update_pending = False
    vehicle.live_rebuild_pending = False
    vehicle.live_update_error = ""
    _stale_vehicle_validation(vehicle)
    if vehicle.preview_built:
        vehicle.preview_message = "Authoring values changed; rebuild the preview"
    update_vehicle_guides(self, context)


def update_vehicle_guides(self, context):
    from .runtime.vehicle_guides import tag_guides_redraw

    tag_guides_redraw()


def update_vehicle_game_camera(self, context):
    from .runtime.vehicle_camera import start_vehicle_camera, stop_vehicle_camera

    scene = getattr(context, "scene", None)
    if scene is None:
        return
    if self.game_camera:
        if not start_vehicle_camera(scene):
            self.game_camera = False
    else:
        stop_vehicle_camera(scene)


def update_vehicle_game_camera_preset(self, context):
    from .runtime.vehicle_camera import snap_vehicle_camera

    scene = getattr(context, "scene", None)
    physx = getattr(scene, "physx", None) if scene is not None else None
    # A running simulation eases the boom and pitch to the new preset; a paused one jumps to it.
    if (
        scene is not None
        and self.game_camera
        and not getattr(physx, "sim_running", False)
    ):
        snap_vehicle_camera(scene)


def _queue_vehicle_live_change(self, context, *, rebuild):
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    vehicle = getattr(scene, "physx_vehicle", None) or self
    _stale_vehicle_validation(vehicle)
    try:
        from .runtime.vehicle_preview import queue_vehicle_live_update

        queue_vehicle_live_update(scene, rebuild=rebuild)
    except Exception as error:
        debug_exception(_LOG, "Could not queue the live vehicle update")
        vehicle.live_update_error = str(error)
    update_vehicle_guides(self, context)


def update_vehicle_live_dynamics(self, context):
    """Edits the running vehicle preview applies in place"""
    _queue_vehicle_live_change(self, context, rebuild=False)


def update_vehicle_live_rebuild(self, context):
    """Rebuild the running vehicle preview after a chassis collider edit"""
    _queue_vehicle_live_change(self, context, rebuild=True)


def _record_search(choices, failure):
    """A search callback offering the (record, label) pairs that hold the typed text"""

    def search(self, context, edit_text):
        try:
            found = choices(self, context)
        except Exception:
            debug_exception(_LOG, failure)
            return []
        text = str(edit_text or "").casefold()
        return [
            (record_id, label)
            for record_id, label in found
            if not text or text in record_id.casefold() or text in label.casefold()
        ]

    return search


_search_base_vehicles = _record_search(
    base_vehicle_choices, "Could not list the base vehicles for the search"
)
_search_record_overrides = _record_search(
    record_override_choices, "Could not list the vehicle variants for the search"
)


def update_vehicle_export_only(self, context):
    scene = getattr(context, "scene", None)
    if scene is None:
        return
    vehicle = getattr(scene, "physx_vehicle", None) or self
    _stale_vehicle_validation(vehicle)


def update_vehicle_kind(self, context):
    archetype = str(getattr(self, "vehicle_archetype", "") or "")
    if self.vehicle_kind == "CAR" and not archetype.startswith("CAR_"):
        self.vehicle_archetype = "CAR_STANDARD"
    elif self.vehicle_kind == "BIKE" and not archetype.startswith("BIKE_"):
        self.vehicle_archetype = "BIKE_KUSANAGI"
    update_vehicle_authoring(self, context)


def _get_engine_max_rpm(self):
    return float(self.engine_max_omega) * 60.0 / (2.0 * math.pi)


def _set_engine_max_rpm(self, value):
    self.engine_max_omega = float(value) * (2.0 * math.pi / 60.0)


class PhysXVehicleAxleProperties(bpy.types.PropertyGroup):
    tire_radius: bpy.props.FloatProperty(
        name="tireRadius",
        description="Cyberpunk wheel dimension; PhysX wheel radius",
        default=0.36,
        min=0.01,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    rim_radius: bpy.props.FloatProperty(
        name="rimRadius",
        description="Cyberpunk visual rim radius; retained for TweakXL export",
        default=0.28,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_export_only,
    )
    tire_width: bpy.props.FloatProperty(
        name="tireWidth",
        description="Cyberpunk wheel dimension; PhysX wheel width",
        default=0.25,
        min=0.01,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    wheel_offset: bpy.props.FloatProperty(
        name="wheelOffset",
        description="Cyberpunk lateral wheel offset; applied to the PhysX wheel centre",
        default=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    mass: bpy.props.FloatProperty(
        name="mass",
        description="Cyberpunk wheel preset mass; PhysX wheel mass",
        default=20.0,
        min=0.01,
        unit="MASS",
        update=update_vehicle_live_dynamics,
    )
    max_braking_torque: bpy.props.FloatProperty(
        name="maxBrakingTorque",
        description="Cyberpunk wheel preset brake torque; PhysX maximum brake torque",
        default=1500.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    logical_suspension_compression_length: bpy.props.FloatProperty(
        name="logicalSuspensionCompressionLength",
        description="Cyberpunk logical suspension compression length used by the preview wheel solver",
        default=0.30,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    visual_suspension_compression_length: bpy.props.FloatProperty(
        name="visualSuspensionCompressionLength",
        description="Cyberpunk visual suspension compression limit; used only as a geometry fallback when no rig displacement is available",
        default=0.30,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    visual_suspension_droop: bpy.props.FloatProperty(
        name="visualSuspensionDroop",
        description="Cyberpunk visual suspension droop; converted to logical droop from the rig suspension angle",
        default=0.10,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    spring_stiffness: bpy.props.FloatProperty(
        name="springStiffness",
        description="Cyberpunk spring rate in kg/mm; runtime spring strength is derived from logical spring length and scene gravity",
        default=35.0,
        min=0.001,
        update=update_vehicle_live_dynamics,
    )
    spring_damping: bpy.props.FloatProperty(
        name="springDamping",
        description="Cyberpunk high-rate compression damping used by the preview wheel solver",
        default=4500.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    spring_rebound_damping: bpy.props.FloatProperty(
        name="springReboundDamping",
        description="Cyberpunk high-rate rebound damping used by the preview wheel solver",
        default=4500.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    tire_friction_coef: bpy.props.FloatProperty(
        name="tireFrictionCoef",
        description="Cyberpunk base tire friction coefficient",
        default=1.5,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    friction_mul_longitudinal: bpy.props.FloatProperty(
        name="frictionMulLongitudinal",
        description="Cyberpunk longitudinal tire-friction multiplier used by the preview wheel solver",
        default=1.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    friction_mul_lateral: bpy.props.FloatProperty(
        name="frictionMulLateral",
        description="Cyberpunk lateral tire-friction multiplier used by the preview wheel solver",
        default=1.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    wheels_vertical_offset: bpy.props.FloatProperty(
        name="wheelsVerticalOffset",
        description="Cyberpunk wheel vertical offset used by the logical suspension origin and visual wheel mapping",
        default=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    extreme_compression_event_scalor: bpy.props.FloatProperty(
        name="extremeCompressionEventScalor",
        description="Cyberpunk extreme-compression spring-force scaling used by the preview wheel solver",
        default=0.7,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    spring_bound_damping_low_rate: bpy.props.FloatProperty(
        name="springBoundDampingLowRate",
        description="Cyberpunk low-rate compression damping used by the preview wheel solver",
        default=0.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    spring_damping_high_rate_compression: bpy.props.FloatProperty(
        name="springDampingHighRateCompression",
        description="Cyberpunk compression depth where nonlinear damping reaches the high rate",
        default=0.5,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    spring_damping_low_rate_compression: bpy.props.FloatProperty(
        name="springDampingLowRateCompression",
        description="Cyberpunk compression depth where nonlinear damping uses the low rate",
        default=0.3,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    spring_rebound_damping_low_rate: bpy.props.FloatProperty(
        name="springReboundDampingLowRate",
        description="Cyberpunk low-rate rebound damping used by the preview wheel solver",
        default=0.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    swaybar_stiffness: bpy.props.FloatProperty(
        name="swaybarStiffness",
        description="Cyberpunk anti-roll stiffness used by the preview wheel solver",
        default=0.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    swaybar_length_scalar: bpy.props.FloatProperty(
        name="swaybarLengthScalar",
        description="Cyberpunk sway-bar lever-length scale used by the preview wheel solver",
        default=1.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    swaybar_displacement_limit: bpy.props.FloatProperty(
        name="swaybarDisplacementLimit",
        description="Cyberpunk sway-bar displacement clamp used by the preview wheel solver",
        default=0.0,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    tender_spring_length: bpy.props.FloatProperty(
        name="tenderSpringLength",
        description="Cyberpunk tender-spring field retained for TweakXL; PhysX 3.4 suspension data has no tender-spring stage",
        default=0.0,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_export_only,
    )
    tire_lateral_slip_effects_mul: bpy.props.FloatProperty(
        name="tireLateralSlipEffectsMul",
        description="Cyberpunk slip-effects field retained for TweakXL; it is not a PhysX tire-force parameter",
        default=1.0,
        min=0.0,
        update=update_vehicle_export_only,
    )
    tire_longitudinal_slip_effects_mul: bpy.props.FloatProperty(
        name="tireLongitudinalSlipEffectsMul",
        description="Cyberpunk slip-effects field retained for TweakXL; it is not a PhysX tire-force parameter",
        default=1.0,
        min=0.0,
        update=update_vehicle_export_only,
    )
    tire_rolling_resistance_coef: bpy.props.FloatProperty(
        name="tireRollingResistanceCoef",
        description="Cyberpunk rolling-resistance coefficient applied by the preview wheel solver",
        default=0.002,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )


class PhysXVehicleWheelRoleProperties(bpy.types.PropertyGroup):
    is_drive: bpy.props.BoolProperty(
        name="isDrive", default=True, update=update_vehicle_live_dynamics
    )
    is_main_brake: bpy.props.BoolProperty(
        name="isMainBrake", default=True, update=update_vehicle_live_dynamics
    )
    is_hand_brake: bpy.props.BoolProperty(
        name="isHandBrake", default=False, update=update_vehicle_live_dynamics
    )


class PhysXVehicleGearItem(bpy.types.PropertyGroup):
    ratio: bpy.props.FloatProperty(
        name="PhysX Ratio Cache",
        description="Derived PhysX ratio retained for migration; Cyberpunk maxSpeed is authoritative",
        default=1.0,
        precision=4,
        options={"HIDDEN"},
        update=update_vehicle_live_dynamics,
    )
    min_speed: bpy.props.FloatProperty(
        name="minSpeed",
        description="Cyberpunk gear minimum vehicle speed; retained losslessly for TweakXL and source-model gearbox work",
        default=0.0,
        min=0.0,
        unit="VELOCITY",
        update=update_vehicle_live_dynamics,
    )
    max_speed: bpy.props.FloatProperty(
        name="maxSpeed",
        description="Cyberpunk gear maximum vehicle speed; the PhysX gear ratio is derived from maxSpeed, maxEngineRPM, and driven-wheel radius",
        default=10.0,
        min=0.001,
        unit="VELOCITY",
        update=update_vehicle_live_dynamics,
    )
    torque_multiplier: bpy.props.FloatProperty(
        name="torqueMultiplier",
        default=1.0,
        min=0.0,
        precision=4,
        update=update_vehicle_live_dynamics,
    )
    min_engine_rpm: bpy.props.FloatProperty(
        name="minEngineRPM",
        default=1200.0,
        min=0.0,
        precision=1,
        update=update_vehicle_live_dynamics,
    )
    max_engine_rpm: bpy.props.FloatProperty(
        name="maxEngineRPM",
        default=6000.0,
        min=1.0,
        precision=1,
        update=update_vehicle_live_dynamics,
    )
    source_record: bpy.props.StringProperty(default="", options={"HIDDEN"})


class PhysXVehicleProperties(bpy.types.PropertyGroup):
    enabled: bpy.props.BoolProperty(
        name="Enable Vehicle", default=False, update=update_vehicle_authoring
    )
    vehicle_kind: bpy.props.EnumProperty(
        name="Vehicle Type",
        items=(
            ("CAR", "Car", "Four-wheel vehicle authoring and PhysX preview"),
            (
                "BIKE",
                "Bike",
                "Two-wheel vehicle authoring, native PhysX preview, and TweakXL export",
            ),
        ),
        default="CAR",
        update=update_vehicle_kind,
    )
    authoring_page: bpy.props.EnumProperty(
        name="Workspace",
        items=(
            ("SETUP", "Setup", "The vehicle's rig or meshes and its game data"),
            ("DYNAMICS", "Wheels", "Chassis, wheels, suspension and grip"),
            ("POWERTRAIN", "Engine", "Engine and gears"),
            ("PREVIEW", "Drive", "Build the vehicle and drive it in the viewport"),
            ("OUTPUT", "Export", "Export the vehicle as a TweakXL record"),
        ),
        default="SETUP",
    )
    ui_show_advanced: bpy.props.BoolProperty(
        name="Advanced",
        description="Show less common settings",
        default=False,
    )
    vehicle_archetype: bpy.props.EnumProperty(
        name="Preset Archetype",
        items=(
            ("CAR_STANDARD", "Standard Car", "Archer Hella road-car handling"),
            ("CAR_SPORT", "Sport Car", "Quadra Turbo sport handling"),
            ("CAR_OFFROAD", "Off-road Car", "Type-66 Nomad off-road handling"),
            ("BIKE_KUSANAGI", "Sport Bike", "Yaiba Kusanagi sport-bike handling"),
            ("BIKE_ARCH", "Road Bike", "Arch road-bike handling"),
            ("BIKE_APOLLO", "Off-road Bike", "Brennan Apollo bike handling"),
        ),
        default="CAR_STANDARD",
        update=update_vehicle_authoring,
    )
    source_mode: bpy.props.EnumProperty(
        name="Source",
        items=(
            (
                "RIG",
                "Imported Rig",
                "Resolve the vehicle from the selected imported MetaRig",
            ),
            (
                "MANUAL",
                "Manual Meshes",
                "Assign a chassis and the required wheel meshes manually",
            ),
        ),
        default="RIG",
        update=update_vehicle_authoring,
    )
    rig: bpy.props.PointerProperty(
        name="Vehicle MetaRig", type=bpy.types.Object, update=update_vehicle_authoring
    )
    appearance_collection: bpy.props.PointerProperty(
        name="Appearance", type=bpy.types.Collection
    )
    front_left_bone: bpy.props.StringProperty(name="Front Left Wheel Bone")
    front_right_bone: bpy.props.StringProperty(name="Front Right Wheel Bone")
    rear_left_bone: bpy.props.StringProperty(name="Rear Left Wheel Bone")
    rear_right_bone: bpy.props.StringProperty(name="Rear Right Wheel Bone")
    front_left_suspension_bone: bpy.props.StringProperty(name="Front Left Suspension")
    front_right_suspension_bone: bpy.props.StringProperty(name="Front Right Suspension")
    rear_left_suspension_bone: bpy.props.StringProperty(name="Rear Left Suspension")
    rear_right_suspension_bone: bpy.props.StringProperty(name="Rear Right Suspension")
    bike_front_bone: bpy.props.StringProperty(name="Front Wheel Bone")
    bike_rear_bone: bpy.props.StringProperty(name="Rear Wheel Bone")
    bike_front_suspension_bone: bpy.props.StringProperty(name="Front Suspension")
    bike_rear_suspension_bone: bpy.props.StringProperty(name="Rear Suspension")
    resolved_object_names: bpy.props.StringProperty(default="[]", options={"HIDDEN"})
    resolved_wheel_groups: bpy.props.StringProperty(default="{}", options={"HIDDEN"})
    resolved_visual_count: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"})
    resolved_wheel_visual_count: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"})
    source_summary: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    validation_state: bpy.props.EnumProperty(
        items=(
            ("NOT_RUN", "Not Validated", "Validation has not been run"),
            ("VALID", "Valid", "Vehicle authoring data passed validation"),
            ("WARNING", "Warnings", "Vehicle is valid with authoring warnings"),
            ("ERROR", "Errors", "Vehicle authoring data contains blocking errors"),
            (
                "STALE",
                "Out of Date",
                "Authoring values changed after the last validation",
            ),
        ),
        default="NOT_RUN",
        options={"SKIP_SAVE"},
    )
    validation_errors: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    validation_warnings: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    vehicle_tweak_root: bpy.props.StringProperty(
        name="Tweak Data Root",
        description=(
            "Optional folder of base .tweak, .yaml, or .yml records that replaces the game's RedMod tweaks folder; "
            "empty uses the Game Directory from the add-on preferences. Project overrides in source/resources apply on top"
        ),
        subtype="DIR_PATH",
    )
    vehicle_resource_root: bpy.props.StringProperty(
        name="Resource Root",
        description="Exported source/raw root containing entity curve and physics resources; empty uses the imported entity root",
        subtype="DIR_PATH",
    )
    game_data_record_override: bpy.props.StringProperty(
        name="Vehicle Record Override",
        description=(
            "The game vehicle record Load Game Data uses instead of the best match for the imported entity; "
            "lists the variants of the Based On vehicle"
        ),
        search=_search_record_overrides,
        search_options={"SUGGESTION"},
    )
    game_data_enabled: bpy.props.BoolProperty(
        name="Use Resolved Game Data",
        default=False,
        update=update_vehicle_authoring,
    )
    game_data_config: bpy.props.StringProperty(default="", options={"HIDDEN"})
    game_data_record: bpy.props.StringProperty(default="")
    game_data_warnings: bpy.props.StringProperty(default="")
    refresh_rig_on_build: bpy.props.BoolProperty(
        name="Refresh Rig on Build",
        description="Resolve the currently visible imported appearance and refit geometry before building the preview",
        default=True,
    )
    chassis: bpy.props.PointerProperty(
        name="Chassis", type=bpy.types.Object, update=update_vehicle_authoring
    )
    front_left: bpy.props.PointerProperty(
        name="Front Left", type=bpy.types.Object, update=update_vehicle_authoring
    )
    front_right: bpy.props.PointerProperty(
        name="Front Right", type=bpy.types.Object, update=update_vehicle_authoring
    )
    rear_left: bpy.props.PointerProperty(
        name="Rear Left", type=bpy.types.Object, update=update_vehicle_authoring
    )
    rear_right: bpy.props.PointerProperty(
        name="Rear Right", type=bpy.types.Object, update=update_vehicle_authoring
    )
    bike_front: bpy.props.PointerProperty(
        name="Front Wheel", type=bpy.types.Object, update=update_vehicle_authoring
    )
    bike_rear: bpy.props.PointerProperty(
        name="Rear Wheel", type=bpy.types.Object, update=update_vehicle_authoring
    )
    tweakxl_record_id: bpy.props.StringProperty(
        name="Record ID",
        description="TweakDB record written by the TweakXL exporter",
        default="Vehicle.mod_vehicle",
    )
    tweakxl_base_record: bpy.props.StringProperty(
        name="Based On",
        description="The game vehicle the exported record inherits from ($base); set when game data is loaded or a base vehicle applied",
        default="",
        search=_search_base_vehicles,
        search_options={"SUGGESTION"},
    )
    tweakxl_add_to_vehicle_list: bpy.props.BoolProperty(
        name="Add to Player Vehicles",
        description="Also append the record to Vehicle.vehicle_list so the player can own and summon it",
        default=False,
    )
    forward_axis: bpy.props.EnumProperty(
        name="Forward Axis",
        items=(
            ("POS_X", "+X", "Chassis local +X is forward"),
            ("NEG_X", "-X", "Chassis local -X is forward"),
            ("POS_Y", "+Y", "Chassis local +Y is forward"),
            ("NEG_Y", "-Y", "Chassis local -Y is forward"),
        ),
        default="POS_Y",
        update=update_vehicle_authoring,
    )
    axle_alignment_tolerance: bpy.props.FloatProperty(
        name="Axle Tolerance",
        default=0.1,
        min=0.001,
        unit="LENGTH",
        update=update_vehicle_authoring,
    )

    axle_authoring_initialized: bpy.props.BoolProperty(
        default=False, options={"HIDDEN"}
    )
    axle_authoring_view: bpy.props.EnumProperty(
        name="Wheel Setup",
        items=(
            (
                "FRONT",
                "Front",
                "Author vehWheelDimensionsSetup.frontPreset and wheelSetup.frontPreset",
            ),
            (
                "REAR",
                "Rear",
                "Author vehWheelDimensionsSetup.backPreset and wheelSetup.backPreset",
            ),
        ),
        default="FRONT",
    )
    front_axle: bpy.props.PointerProperty(type=PhysXVehicleAxleProperties)
    rear_axle: bpy.props.PointerProperty(type=PhysXVehicleAxleProperties)
    wheel_role_lf: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)
    wheel_role_rf: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)
    wheel_role_lb: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)
    wheel_role_rb: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)
    wheel_role_front: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)
    wheel_role_back: bpy.props.PointerProperty(type=PhysXVehicleWheelRoleProperties)

    chassis_dims: bpy.props.FloatVectorProperty(
        name="Dimensions",
        description="Vehicle-frame width, length, and height",
        default=(1.8, 4.0, 1.2),
        min=0.01,
        unit="LENGTH",
        update=update_vehicle_live_rebuild,
    )
    chassis_shape_offset: bpy.props.FloatVectorProperty(
        name="Collider Center",
        default=(0.0, 0.0, 0.0),
        subtype="TRANSLATION",
        update=update_vehicle_live_rebuild,
    )
    chassis_mass: bpy.props.FloatProperty(
        name="chassis_mass",
        default=1500.0,
        min=1.0,
        unit="MASS",
        update=update_vehicle_live_dynamics,
    )
    total_mass: bpy.props.FloatProperty(
        name="total_mass",
        description="Cyberpunk drive-model total mass retained for TweakXL authoring",
        default=1500.0,
        min=1.0,
        unit="MASS",
        update=update_vehicle_export_only,
    )
    chassis_cm_offset: bpy.props.FloatVectorProperty(
        name="center_of_mass_offset",
        default=(0.0, 0.0, -0.35),
        subtype="TRANSLATION",
        update=update_vehicle_live_dynamics,
    )
    use_chassis_inertia: bpy.props.BoolProperty(
        name="Author momentOfInertia",
        description="Use the authored Cyberpunk momentOfInertia instead of the PhysX preview's box-derived inertia",
        default=False,
        update=update_vehicle_live_dynamics,
    )
    chassis_inertia: bpy.props.FloatVectorProperty(
        name="momentOfInertia",
        description="Cyberpunk vehDriveModelData momentOfInertia mapped directly to the PhysX chassis mass-space inertia tensor",
        default=(1000.0, 2000.0, 2500.0),
        min=0.001,
        size=3,
        update=update_vehicle_live_dynamics,
    )
    air_resistance_factor: bpy.props.FloatProperty(
        name="airResistanceFactor",
        description="Cyberpunk aerodynamic resistance factor; retained for game authoring",
        default=1.0,
        min=0.0,
        update=update_vehicle_export_only,
    )
    braking_friction_factor: bpy.props.FloatProperty(
        name="brakingFrictionFactor",
        description="Cyberpunk braking friction factor; retained for game authoring",
        default=1.0,
        min=0.0,
        update=update_vehicle_export_only,
    )
    turning_roll_factor: bpy.props.FloatProperty(
        name="turningRollFactor",
        description="Cyberpunk turning roll factor used by tire angular impulse scaling",
        default=1.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    wheel_turn_max_add_per_second: bpy.props.FloatProperty(
        name="wheelTurnMaxAddPerSecond",
        description="Cyberpunk steering input rise rate in degrees per second; maps to PhysX steering smoothing",
        default=90.0,
        min=0.01,
        update=update_vehicle_live_dynamics,
    )
    wheel_turn_max_sub_per_second: bpy.props.FloatProperty(
        name="wheelTurnMaxSubPerSecond",
        description="Cyberpunk steering input fall rate in degrees per second; maps to PhysX steering smoothing",
        default=90.0,
        min=0.01,
        update=update_vehicle_live_dynamics,
    )
    com_height_ratio: bpy.props.FloatProperty(
        name="Auto CoM Height", default=0.35, min=0.0, max=1.0, subtype="FACTOR"
    )

    wheel_radius: bpy.props.FloatProperty(
        name="Radius",
        default=0.36,
        min=0.01,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    wheel_width: bpy.props.FloatProperty(
        name="Width",
        default=0.25,
        min=0.01,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    wheel_mass: bpy.props.FloatProperty(
        name="Mass",
        default=20.0,
        min=0.01,
        unit="MASS",
        update=update_vehicle_live_dynamics,
    )
    auto_wheel_moi: bpy.props.BoolProperty(
        name="Auto MOI", default=True, update=update_vehicle_live_dynamics
    )
    wheel_moi: bpy.props.FloatProperty(
        name="Moment of Inertia",
        default=1.3,
        min=0.001,
        update=update_vehicle_live_dynamics,
    )
    wheel_damping_rate: bpy.props.FloatProperty(
        name="Damping Rate", default=0.25, min=0.0, update=update_vehicle_live_dynamics
    )
    max_brake_torque: bpy.props.FloatProperty(
        name="Brake Torque",
        default=1500.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    rear_handbrake_torque: bpy.props.FloatProperty(
        name="Handbrake Torque",
        default=3000.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    front_steer_angle: bpy.props.FloatProperty(
        name="Maximum Steering",
        default=math.radians(35.0),
        min=0.0,
        max=math.radians(80.0),
        subtype="ANGLE",
        update=update_vehicle_live_dynamics,
    )

    suspension_max_compression: bpy.props.FloatProperty(
        name="Compression",
        default=0.3,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    suspension_max_droop: bpy.props.FloatProperty(
        name="Droop",
        default=0.1,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_live_dynamics,
    )
    suspension_spring_strength: bpy.props.FloatProperty(
        name="Spring Strength",
        default=35000.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    suspension_damper_rate: bpy.props.FloatProperty(
        name="Damper Rate", default=4500.0, min=0.0, update=update_vehicle_live_dynamics
    )
    tire_friction: bpy.props.FloatProperty(
        name="Tire Friction", default=1.5, min=0.01, update=update_vehicle_live_dynamics
    )

    engine_peak_torque: bpy.props.FloatProperty(
        name="engineMaxTorque",
        default=500.0,
        min=0.01,
        update=update_vehicle_live_dynamics,
    )
    engine_moi: bpy.props.FloatProperty(
        name="flyWheelMomentOfInertia",
        description="Cyberpunk engine flywheel moment of inertia mapped to PxVehicleEngineData::mMOI",
        default=1.0,
        min=0.001,
        update=update_vehicle_live_dynamics,
    )
    engine_resistance_torque: bpy.props.FloatProperty(
        name="resistanceTorque",
        description="Cyberpunk engine resistance torque mapped to PhysX engine damping at max engine speed",
        default=90.0,
        min=0.0,
        update=update_vehicle_live_dynamics,
    )
    engine_max_omega: bpy.props.FloatProperty(
        name="Maximum Omega",
        description="PhysX engine maximum angular speed in radians per second",
        default=600.0,
        min=0.01,
        update=update_vehicle_live_dynamics,
    )
    engine_max_rpm: bpy.props.FloatProperty(
        name="Maximum Engine Speed",
        description="Authoring view of the PhysX maximum engine speed",
        min=1.0,
        precision=0,
        get=_get_engine_max_rpm,
        set=_set_engine_max_rpm,
    )
    gear_switch_time: bpy.props.FloatProperty(
        name="gearChangeTime",
        default=0.5,
        min=0.0,
        unit="TIME",
        update=update_vehicle_live_dynamics,
    )
    final_gear_torque_decimation: bpy.props.FloatProperty(
        name="finalGearTorqueDecimationScalor",
        description="Cyberpunk final-gear torque decimation applied to the highest forward gear",
        default=1.0,
        min=0.0,
        precision=4,
        update=update_vehicle_live_dynamics,
    )
    gears: bpy.props.CollectionProperty(type=PhysXVehicleGearItem)
    gear_index: bpy.props.IntProperty(default=0, min=0)
    clutch_strength: bpy.props.FloatProperty(
        name="Clutch Strength",
        description="PhysX clutch coupling strength between engine and drivetrain",
        default=10.0,
        min=0.01,
        update=update_vehicle_live_dynamics,
    )
    ackermann_accuracy: bpy.props.FloatProperty(
        name="Ackermann Accuracy",
        description="PhysX Ackermann steering correction; 1.0 applies the full geometric solution",
        default=1.0,
        min=0.0,
        max=1.0,
        subtype="FACTOR",
        update=update_vehicle_live_dynamics,
    )
    auto_gears: bpy.props.BoolProperty(
        name="Automatic Gears", default=True, update=update_vehicle_live_dynamics
    )
    bike_max_lean_angle: bpy.props.FloatProperty(
        name="Maximum Lean",
        default=math.radians(39.0),
        min=math.radians(1.0),
        max=math.radians(80.0),
        subtype="ANGLE",
        update=update_vehicle_live_dynamics,
    )
    bike_tilt_pid: bpy.props.FloatVectorProperty(
        name="Lean PID",
        default=(2.5, 0.2, 0.0),
        min=0.0,
        size=3,
        update=update_vehicle_live_dynamics,
    )
    bike_tilt_speed: bpy.props.FloatProperty(
        name="Lean Rate",
        default=math.radians(103.0),
        min=0.01,
        subtype="ANGLE",
        update=update_vehicle_live_dynamics,
    )
    bike_tilt_return_speed: bpy.props.FloatProperty(
        name="Return Lean Rate",
        default=math.radians(83.0),
        min=0.01,
        subtype="ANGLE",
        update=update_vehicle_live_dynamics,
    )
    bike_tilt_custom_speed: bpy.props.FloatProperty(
        name="Custom Lean Rate",
        default=math.radians(150.0),
        min=0.01,
        subtype="ANGLE",
        update=update_vehicle_export_only,
    )
    bike_max_com_long_offset: bpy.props.FloatProperty(
        name="Maximum Longitudinal CoM Offset",
        default=0.6,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_export_only,
    )
    bike_min_com_long_offset: bpy.props.FloatProperty(
        name="Minimum Longitudinal CoM Offset",
        default=0.7,
        min=0.0,
        unit="LENGTH",
        update=update_vehicle_export_only,
    )
    bike_com_offset_damp_factor: bpy.props.FloatProperty(
        name="CoM Offset Damping",
        default=0.25,
        min=0.0,
        update=update_vehicle_export_only,
    )
    preview_auto_ground: bpy.props.BoolProperty(name="Add Preview Ground", default=True)

    wheelbase: bpy.props.FloatProperty(
        name="Wheelbase", default=0.0, options={"SKIP_SAVE"}, unit="LENGTH"
    )
    track_width: bpy.props.FloatProperty(
        name="Track Width", default=0.0, options={"SKIP_SAVE"}, unit="LENGTH"
    )

    throttle: bpy.props.FloatProperty(
        name="Throttle", default=0.0, min=0.0, max=1.0, subtype="FACTOR"
    )
    brake: bpy.props.FloatProperty(
        name="Brake / Reverse", default=0.0, min=0.0, max=1.0, subtype="FACTOR"
    )
    steer: bpy.props.FloatProperty(
        name="Steering",
        description="Steering input: -1 full left, +1 full right",
        default=0.0,
        min=-1.0,
        max=1.0,
        subtype="FACTOR",
    )
    handbrake: bpy.props.FloatProperty(
        name="Handbrake", default=0.0, min=0.0, max=1.0, subtype="FACTOR"
    )

    vehicle_handle: bpy.props.StringProperty(default="0", options={"SKIP_SAVE"})
    preview_built: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    preview_dirty: bpy.props.BoolProperty(default=True, options={"SKIP_SAVE"})
    preview_message: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    live_update_supported: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    live_update_pending: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    live_rebuild_pending: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    show_authoring_guides: bpy.props.BoolProperty(
        name="Authoring Guides",
        description="Draw the suspension springs, centre of mass and moment of inertia in the viewport",
        default=False,
        update=update_vehicle_guides,
    )
    game_camera: bpy.props.BoolProperty(
        name="Game Camera",
        description="Follow the vehicle in the largest 3D viewport with a chase camera driven by its camera presets",
        default=False,
        options={"SKIP_SAVE"},
        update=update_vehicle_game_camera,
    )
    game_camera_height: bpy.props.EnumProperty(
        name="Camera Height",
        description="Height of the game camera preset",
        items=(
            ("High", "High", "The game's high camera presets"),
            ("Low", "Low", "The game's low camera presets"),
        ),
        default="High",
        update=update_vehicle_game_camera_preset,
    )
    game_camera_distance: bpy.props.EnumProperty(
        name="Camera Distance",
        description="Distance of the game camera preset",
        items=(
            ("Close", "Close", "The game's close camera presets"),
            ("Medium", "Medium", "The game's medium camera presets"),
            ("Far", "Far", "The game's far camera presets"),
        ),
        default="Close",
        update=update_vehicle_game_camera_preset,
    )
    live_update_error: bpy.props.StringProperty(default="", options={"SKIP_SAVE"})
    forward_speed: bpy.props.FloatProperty(default=0.0, options={"SKIP_SAVE"})
    sideways_speed: bpy.props.FloatProperty(default=0.0, options={"SKIP_SAVE"})
    engine_omega: bpy.props.FloatProperty(default=0.0, options={"SKIP_SAVE"})
    linear_velocity: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0), size=3, options={"SKIP_SAVE"}
    )
    angular_velocity: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0), size=3, options={"SKIP_SAVE"}
    )
    current_gear: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"})
    target_gear: bpy.props.IntProperty(default=0, options={"SKIP_SAVE"})
    vehicle_in_air: bpy.props.BoolProperty(default=False, options={"SKIP_SAVE"})
    bike_lean: bpy.props.FloatProperty(
        default=0.0, options={"SKIP_SAVE"}, subtype="ANGLE"
    )
    bike_target_lean: bpy.props.FloatProperty(
        default=0.0, options={"SKIP_SAVE"}, subtype="ANGLE"
    )
    wheel_contact_strength: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )
    wheel_compression: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}, unit="LENGTH"
    )
    wheel_suspension_velocity: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}, unit="VELOCITY"
    )
    wheel_spring_force: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )
    wheel_normal_load: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )
    wheel_longitudinal_slip: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}, unit="VELOCITY"
    )
    wheel_lateral_slip: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}, unit="VELOCITY"
    )
    wheel_longitudinal_force: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )
    wheel_lateral_force: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )
    wheel_effective_friction: bpy.props.FloatVectorProperty(
        default=(0.0, 0.0, 0.0, 0.0), size=4, options={"SKIP_SAVE"}
    )


COLLISION_PROPERTY_CLASSES = (
    *DANGLE_PROPERTY_CLASSES,
    PhysXShapeItem,
    PhysXActorItem,
    PhysXObjectProperties,
    PhysXSceneProperties,
    PhysXVehicleAxleProperties,
    PhysXVehicleWheelRoleProperties,
    PhysXVehicleGearItem,
    PhysXVehicleProperties,
)
