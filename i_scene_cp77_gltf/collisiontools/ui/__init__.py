from .dangle_lists import (
    DANGLE_UL_chains,
    DANGLE_UL_collision_shapes,
    DANGLE_UL_dangle_nodes,
    DANGLE_UL_particles,
    DANGLE_UL_rigs,
)
from .panels import CP77_PT_PhysicsTools
from .physx_gizmos import PhysXToolsGizmoGroup
from .physx_lists import (
    PHYSX_UL_actor_list,
    PHYSX_UL_shape_list,
    PHYSX_UL_vehicle_gear_list,
)

COLLISION_UI_CLASSES = (
    DANGLE_UL_rigs,
    DANGLE_UL_dangle_nodes,
    DANGLE_UL_chains,
    DANGLE_UL_particles,
    DANGLE_UL_collision_shapes,
    PHYSX_UL_actor_list,
    PHYSX_UL_shape_list,
    PHYSX_UL_vehicle_gear_list,
    PhysXToolsGizmoGroup,
    CP77_PT_PhysicsTools,
)
