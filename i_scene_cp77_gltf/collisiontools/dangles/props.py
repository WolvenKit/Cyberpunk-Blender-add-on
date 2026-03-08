import bpy
from bpy.props import (
    StringProperty, BoolProperty, FloatProperty, EnumProperty,
    CollectionProperty, FloatVectorProperty, PointerProperty, IntProperty,
)

ENUM_SOLVER_TYPE = [
    ("DYNG", "Dyng (Particles)", "Particle-based dynamic bone simulation"),
    ("PENDULUM", "Pendulum", "Simple pendulum per bone"),
    ("SPRING", "Spring", "Spring-mass per bone"),
    ("PBD", "Position Projection", "Iterative position projection (PBD-like)"),
    ("SINGLE", "Single Bone", "Single bone lightweight solver"),
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

ENUM_PENDULUM_CONSTRAINT_TYPE = [
    ("CONE", "Cone", "Constrain within a circular aperture"),
    ("HINGE_PLANE", "HingePlane", "Constrain strictly to a 2D disk slice"),
    ("HALF_CONE", "HalfCone", "Constrain to a 180-degree hemispherical cone"),
]

ENUM_PENDULUM_PROJECTION_TYPE = [
    ("DISABLED", "Disabled", "No projection"),
    ("SHORTEST_PATH_ROTATIONAL", "ShortestPathRotational", "Rotational projection to nearest surface"),
    ("DIRECTED_ROTATIONAL", "DirectedRotational", "Rotational projection along directed axis"),
]

ENUM_COLLISION_SHAPE_TYPE = [
    ("SPHERE", "Sphere", "Standard spherical collider"),
    ("CAPSULE", "Capsule", "Capsule collider (cylinder with hemispheres)"),
]

class DANGLE_ConstraintLinkConfig(bpy.types.PropertyGroup):
    target_bone: StringProperty(name="Target Bone")
    link_type: EnumProperty(name="Link Type", items=ENUM_DYNG_LINK_TYPE, default="FIXED")
    lower_ratio: FloatProperty(name="Lower Bound (%)", default=100.0, min=0.0)
    upper_ratio: FloatProperty(name="Upper Bound (%)", default=100.0, min=0.0)

    explicit_rest_distance: FloatProperty(
        name="Rest Distance", default=0.0, min=0.0,
        description="Cached reference-pose distance (0 = compute from pose)",
    )
    stiffness: FloatProperty(
        name="Stiffness", default=1.0, min=0.0, max=1.0,
        description="Stiffness",
    )

    look_at_axis: FloatVectorProperty(
        name="Look At Axis", size=3, default=(0.0, 1.0, 0.0),
        description="Axis on bone1 that is rotated to point at bone2",
    )

class DANGLE_ConstraintEllipsoidConfig(bpy.types.PropertyGroup):
    target_bone: StringProperty(name="Center Bone")
    radius: FloatProperty(name="Radius", default=0.1, min=0.001)
    scale1: FloatProperty(name="Scale 1 (Z-)", default=1.0, min=0.001)
    scale2: FloatProperty(name="Scale 2 (Z+)", default=1.0, min=0.001)

    ellipsoid_transform_ls_quat: FloatVectorProperty(
        name="Ellipsoid Transform LS (wxyz)", size=4,
        default=(1.0, 0.0, 0.0, 0.0),
        description="Local-space rotation offset for ellipsoid (quaternion wxyz)",
    )
    ellipsoid_transform_ls_offset: FloatVectorProperty(
        name="Ellipsoid Transform LS Offset", size=3,
        default=(0.0, 0.0, 0.0),
        description="Local-space translation offset for ellipsoid",
    )

class DANGLE_ConstraintPendulumConfig(bpy.types.PropertyGroup):
    target_bone: StringProperty(name="Attachment Bone")
    constraint_type: EnumProperty(
        name="Shape", items=ENUM_PENDULUM_CONSTRAINT_TYPE, default="CONE",
    )
    half_aperture_angle: FloatProperty(
        name="Half Aperture Angle", default=45.0, min=0.0, max=180.0,
        description="HALF of maximum angle between generating lines",
    )
    projection_type: EnumProperty(
        name="Projection", items=ENUM_PENDULUM_PROJECTION_TYPE, default="DISABLED",
    )

    cone_collision_radius: FloatProperty(
        name="Cone Capsule Radius", default=0.0, min=0.0,
        description="Radius of the cone constraint's collision capsule",
    )
    cone_collision_height: FloatProperty(
        name="Cone Capsule Height Extent", default=0.0, min=0.0,
        description="Height extent of the cone constraint's collision capsule",
    )

    cone_transform_ls_quat: FloatVectorProperty(
        name="Cone Transform LS (wxyz)", size=4,
        default=(1.0, 0.0, 0.0, 0.0),
        description="Local-space rotation for the cone shape (quaternion wxyz)",
    )

class DANGLE_CollisionShape(bpy.types.PropertyGroup):
    name: StringProperty(name="Shape Name", default="Shape")
    bone_name: StringProperty(name="Attached Bone")
    shape_type: EnumProperty(name="Type", items=ENUM_COLLISION_SHAPE_TYPE, default="SPHERE")
    radius: FloatProperty(name="Radius", default=0.05, min=0.0)
    height_extent: FloatProperty(
        name="Z Box Extent", default=0.1, min=0.0,
        description="Box half-extent along Z axis (most common capsule axis)",
    )
    x_box_extent: FloatProperty(
        name="X Box Extent", default=0.0, min=0.0,
        description="Box half-extent along X axis",
    )
    y_box_extent: FloatProperty(
        name="Y Box Extent", default=0.0, min=0.0,
        description="Box half-extent along Y axis",
    )
    offset_ls: FloatVectorProperty(name="Offset (LS)", size=3, default=(0.0, 0.0, 0.0))
    rotation_ls_quat: FloatVectorProperty(
        name="Rotation LS (wxyz)", size=4, default=(1.0, 0.0, 0.0, 0.0),
        description="Local-space rotation for collision shape (quaternion wxyz)",
    )

class DANGLE_Particle(bpy.types.PropertyGroup):
    bone_name: StringProperty(name="Bone")

    mass: FloatProperty(name="Mass", default=1.0, min=0.001)
    damping: FloatProperty(name="Damping", default=1.0, min=0.0)
    pull_force: FloatProperty(name="Pull Force Factor", default=0.0, min=0.0)
    is_pinned: BoolProperty(
        name="Pinned (Skip Physics)", default=False,
        description="When set, particle follows animation, not simulation",
    )

    capsule_radius: FloatProperty(name="Capsule Radius", default=0.0, min=0.0)
    capsule_height: FloatProperty(name="Capsule Height Extent", default=0.0, min=0.0)
    capsule_axis_ls: FloatVectorProperty(
        name="Capsule Axis (LS)", size=3, default=(0.5, 0.0, 0.0),
    )
    dyng_projection_type: EnumProperty(
        name="Dyng Projection", items=ENUM_DYNG_PARTICLE_PROJECTION_TYPE,
        default="SHORTEST_PATH",
    )
    pos_projection_type: EnumProperty(
        name="Pos Projection", items=ENUM_POSITION_PROJECTION_TYPE,
        default="SHORTEST_PATH",
    )
    direction_reference_bone: StringProperty(name="Direction Reference Bone")

    link_constraints: CollectionProperty(type=DANGLE_ConstraintLinkConfig)
    ellipsoid_constraints: CollectionProperty(type=DANGLE_ConstraintEllipsoidConfig)
    pendulum_constraints: CollectionProperty(type=DANGLE_ConstraintPendulumConfig)

class DANGLE_DragNode(bpy.types.PropertyGroup):
    bone_name: StringProperty(
        name="Bone",
        description="The bone to apply drag to",
    )
    simulation_fps: FloatProperty(
        name="Simulation FPS", default=120.0, min=1.0, max=240.0,
        description="Internal simulation rate for the drag integrator",
    )
    source_speed_multiplier: FloatProperty(
        name="Speed Multiplier", default=6.0, min=0.001,
        description="Catch-up rate — higher = faster convergence, less visible lag",
    )
    has_overshoot: BoolProperty(
        name="Has Overshoot", default=False,
        description="Enable velocity overshoot detection",
    )
    overshoot_detection_min_speed: FloatProperty(
        name="Overshoot Min Speed", default=0.4, min=0.0,
    )
    overshoot_detection_max_speed: FloatProperty(
        name="Overshoot Max Speed", default=4.0, min=0.0,
    )
    overshoot_duration: FloatProperty(
        name="Overshoot Duration", default=1.0, min=0.0,
    )

    use_steps: BoolProperty(
        name="Use Steps", default=False,
        description="When active, target moves in discrete steps",
    )
    steps_target_speed_multiplier: FloatProperty(
        name="Steps Speed Multiplier", default=10000.0, min=0.001,
        description="Speed of target point when step movement is active",
    )
    time_between_steps: FloatProperty(
        name="Time Between Steps", default=0.1, min=0.001,
        description="Duration of interval between steps (target follows bone)",
    )
    time_in_step: FloatProperty(
        name="Time In Step", default=0.1, min=0.001,
        description="Duration of step (target frozen)",
    )

class DANGLE_Chain(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="Chain")
    solver: EnumProperty(name="Solver", items=ENUM_SOLVER_TYPE, default="DYNG")

    particles: CollectionProperty(type=DANGLE_Particle)
    active_particle_index: IntProperty(name="Active Particle", default=0)

class DANGLE_DangleNode(bpy.types.PropertyGroup):
    name: StringProperty(name="Name", default="DangleNode")

    alpha: FloatProperty(
        name="Alpha Blend Weight", default=1.0, min=0.0, max=1.0,
    )
    rotate_parent_to_look_at: BoolProperty(
        name="Rotate Parent to Look At", default=True,
    )
    look_at_axis: FloatVectorProperty(
        name="Look At Axis", size=3, default=(0.0, 1.0, 0.0),
        description="Bone axis rotated to point at dangle",
    )

    substep_time: FloatProperty(
        name="Substep Time", default=0.01, min=0.005, max=0.1,
        description="Seconds per physics substep for this node",
    )
    solver_iterations: IntProperty(
        name="Solver Iterations", default=2, min=2, max=8, step=2,
        description="Constraint solver iteration count (internal, must be even)",
    )
    imported_solver_iterations: IntProperty(
        name="Imported Solver Iterations", default=0, min=0,
        description="Original solver iterations",
    )

    chains: CollectionProperty(type=DANGLE_Chain)
    active_chain: IntProperty(name="Active Chain", default=0)

    collision_shapes: CollectionProperty(type=DANGLE_CollisionShape)

class DANGLE_AddonState(bpy.types.PropertyGroup):
    is_dangle_rig: BoolProperty(name="Is Dangle Rig", default=False)
    is_playing: BoolProperty(name="Preview Playing", default=False)

    external_force_ws: FloatVectorProperty(
        name="External Force (WS)", size=3, default=(0.0, 0.0, 0.0),
    )

    substep_time: FloatProperty(
        name="Substep Time", default=0.01, min=0.005, max=0.1,
        description="Global seconds per physics substep",
    )
    substeps: IntProperty(
        name="Substeps (legacy)", default=1, min=1, max=10,
        description="Legacy substep count",
    )
    solver_iterations: IntProperty(
        name="Solver Iterations", default=2, min=2, max=8, step=2,
        description="Global solver iteration count (internal, must be even)",
    )
    imported_solver_iterations: IntProperty(
        name="Imported Solver Iterations", default=0, min=0,
        description="Original solver iterations",
    )

    collision_shapes: CollectionProperty(type=DANGLE_CollisionShape)
    active_shape_index: IntProperty(name="Active Shape", default=0)

    dangle_nodes: CollectionProperty(type=DANGLE_DangleNode)
    active_dangle_node: IntProperty(name="Active Dangle Node", default=0)

    drag_nodes: CollectionProperty(type=DANGLE_DragNode)

    show_global_body_shapes: BoolProperty(
        name="Body Collision Shapes", default=True,
        description="Master toggle for body collision shape overlays",
    )
    show_global_capsules: BoolProperty(
        name="Particle Capsules", default=True,
        description="Master toggle for particle collision capsule overlays",
    )
    show_global_constraints: BoolProperty(
        name="Link Constraints", default=True,
        description="Master toggle for distance link overlays",
    )
    show_global_cones: BoolProperty(
        name="Cone Constraints", default=True,
        description="Master toggle for cone/pendulum constraint overlays",
    )
    show_global_velocity: BoolProperty(
        name="Velocity Vectors", default=False,
        description="Master toggle for velocity debug vectors",
    )

classes = (
    DANGLE_ConstraintLinkConfig,
    DANGLE_ConstraintEllipsoidConfig,
    DANGLE_ConstraintPendulumConfig,
    DANGLE_CollisionShape,
    DANGLE_Particle,
    DANGLE_DragNode,
    DANGLE_Chain,
    DANGLE_DangleNode,
    DANGLE_AddonState,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Object.dangle_state = PointerProperty(type=DANGLE_AddonState)
    bpy.types.Scene.dangle_active_rig_index = IntProperty(default=0)

def unregister():
    del bpy.types.Scene.dangle_active_rig_index
    del bpy.types.Object.dangle_state
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)