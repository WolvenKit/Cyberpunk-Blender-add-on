"""
Python-side facade for the native dangle solver.

Translates between DyngSimulator's RNA-backed layout (as found in core.py) and
the topology dict format the C++ Solver expects. This module is the only place
that knows about both data shapes; once it works, core.py can route through
NativeSolverBackend opaquely.

The module is import-safe outside Blender: dangle_native is the only mandatory
import; mathutils and bpy are lazily imported only inside step()-time methods
that need them, so a parity harness can construct topology dicts from canned
data without pulling in the full Blender chain.

Field-name mapping (DyngSimulator -> topology dict):

  sim.particles                       -> topology['particles']
  sim.bone_names                      -> bone-index lookup table
  sim._particle_node_idx              -> particle.node_idx
  sim._node_iters / state.dangle_nodes -> topology['nodes']
  sim.col_shapes (list of dicts from compile_collision_shapes)
                                      -> topology['collision_shapes']
  sim.link_idx_a, .link_idx_b, ...    -> topology['links']
  sim.ell_idx, .ell_radii, ...        -> topology['ellipsoids']
  sim.cone_idx, .cone_attach, ...     -> topology['cones']

Gravity is read fresh each frame from `bpy.context.scene.physx.gravity`
and converted to armature/model space through the shared coordinate contract
before being marshalled to the native solver.
"""

import numpy as np

try:
    from . import dangle_native as _native
except ImportError:
    # Flat-path fallback for sandbox testing outside the addon package.
    # In Blender this branch should never trigger; if it does, the import
    # below will raise and the failure will be visible.
    import dangle_native as _native


# Particle-level dyng projection type. Three states.
_PARTICLE_PROJ_TYPE_MAP = {
    'DISABLED': 0,
    'SHORTEST_PATH': 1,
    'DIRECTED': 2,
}

# Cone-level pendulum projection type. Five states (rotational variants
# trigger the cone collision path; rigs in active use today are all DISABLED).
_CONE_PROJ_TYPE_MAP = {
    'DISABLED': 0,
    'SHORTEST_PATH_ROTATIONAL': 1,
    'DIRECTED_ROTATIONAL': 2,
}

_LINK_TYPE_MAP = {
    'FIXED': 0,
    'VARIABLE': 1,
    'GREATER': 2,
    'CLOSER': 3,
}

_CONSTRAINT_TYPE_MAP = {
    'CONE': 0,
    'HINGE_PLANE': 1,
    'HALF_CONE': 2,
}


def _matrix_to_flat(mat):
    """
    Convert a Blender mathutils.Matrix or numpy 4x4 to a 16-float column-major
    flat array. The C++ side expects column-major (matching the convention
    used in PhysX / glm); we transpose at the marshalling boundary.
    """
    if hasattr(mat, 'to_4x4'):
        m = np.array(mat.to_4x4(), dtype=np.float32)
    else:
        m = np.asarray(mat, dtype=np.float32).reshape(4, 4)
    return np.ascontiguousarray(m.T.reshape(16))


def _capture_bone_matrices_full(sim):
    """
    Build a (N*16,) column-major matrix array from the simulator's tracked
    bones, reading full 4x4 pose matrices (not just translation). Used both
    for compile-time init_state and per-frame step.

    sim.bone_names is the canonical bone list (particles + extra collision-
    shape-owner bones). Index N is `bone_names[N]`.
    """
    n = len(sim.bone_names)
    out = np.zeros(n * 16, dtype=np.float32)
    for i, bn in enumerate(sim.bone_names):
        pb = sim.arm_obj.pose.bones.get(bn)
        if pb is None:
            mat = np.eye(4, dtype=np.float32)
        else:
            mat = np.array(pb.matrix, dtype=np.float32)
        out[i*16:(i+1)*16] = mat.T.flatten()
    return out


class NativeSolverBackend:
    """
    Per-rig native solver wrapper.

    Lifecycle:
        backend = NativeSolverBackend()
        backend.compile(sim)                   # once per topology change
        backend.init_state(sim)                # once after compile
        backend.update_runtime_params(sim)     # once per frame
        new_pos = backend.step(prev_b, cur_b, dt)  # once per frame
    """

    def __init__(self):
        self._solver = _native.Solver()
        self._compiled = False
        self._num_tracked_bones = 0

    # ------------------------------------------------------------------ compile

    def compile(self, sim):
        topology = self._build_topology(sim)
        self._solver.compile(topology)
        self._compiled = True
        self._num_tracked_bones = topology['num_tracked_bones']

    def init_state(self, sim):
        if not self._compiled:
            raise RuntimeError("compile() must be called before init_state()")
        bone_mats = _capture_bone_matrices_full(sim)
        self._solver.init_state(bone_mats)

    def teleport(self, sim):
        if not self._compiled:
            raise RuntimeError("compile() must be called before teleport()")
        bone_mats = _capture_bone_matrices_full(sim)
        self._solver.teleport(bone_mats)

    # ------------------------------------------------------------------ step

    def update_runtime_params(self, sim):
        if not self._compiled:
            return

        n = sim.num_particles
        mass = np.array(
            [max(0.001, p.mass) for p in sim.particles], dtype=np.float32
        )
        damping = np.array(
            [p.damping for p in sim.particles], dtype=np.float32
        )
        pull_force = np.array(
            [p.pull_force for p in sim.particles], dtype=np.float32
        )
        active = sim.active_mask[:n].astype(np.uint8, copy=False)
        pinned = np.array(
            [1 if p.is_pinned else 0 for p in sim.particles], dtype=np.uint8
        )

        # Compute MS-rotated gravity and external force from world-space
        # values. The native solver treats these as MS-domain values; the
        # field names `gravity_ws` / `external_accel_ws` are historical and
        # the marshalling layer simply forwards whatever vectors we pass.
        import bpy
        from mathutils import Vector
        from . import spaces
        physx_grav = (
            bpy.context.scene.physx.gravity if bpy.context
            else Vector((0.0, 0.0, -9.81))
        )
        gravity_ms = spaces.world_direction_to_model(
            sim.arm_obj, physx_grav
        )
        external_ms = spaces.world_direction_to_model(
            sim.arm_obj, sim.state.external_force_ws
        )

        self._solver.update_runtime_params({
            'particle_mass': mass,
            'particle_damping': damping,
            'particle_pull_force': pull_force,
            'particle_active': active,
            'particle_pinned': pinned,
            'gravity_ws': list(gravity_ms),
            'external_accel_ws': list(external_ms),
        })

    def step(self, prev_bone_matrices, cur_bone_matrices, frame_dt):
        return self._solver.step(
            prev_bone_matrices, cur_bone_matrices, frame_dt
        )

    # ------------------------------------------------------------------ topology

    def _build_topology(self, sim):
        from . import spaces
        bone_names = list(sim.bone_names)
        num_tracked_bones = len(bone_names)
        bone_idx_map = {n: i for i, n in enumerate(bone_names)}

        # Nodes: read from sim.state.dangle_nodes (RNA), keep only the fields
        # the native solver currently consumes (solver_iterations, substep_time).
        # alpha and rotate_parent_to_look_at are reserved fields that are not
        # yet read by the C++ side; included for forward compatibility.
        nodes = []
        for dnode in sim.state.dangle_nodes:
            nodes.append({
                'solver_iterations': max(1, int(dnode.solver_iterations)),
                'substep_time': max(0.001, float(dnode.substep_time)),
                'alpha': float(dnode.alpha),
                'rotate_parent_to_look_at': bool(
                    dnode.rotate_parent_to_look_at
                ),
                'look_at_axis': list(
                    spaces.re_axis_to_blender_bone(
                        dnode.look_at_axis, sim.arm_obj
                    )
                ),
            })
        if not nodes:
            nodes.append({
                'solver_iterations': 4,
                'substep_time': 1.0 / 60.0,
                'alpha': 1.0,
                'rotate_parent_to_look_at': False,
                'look_at_axis': [0.0, 0.0, 1.0],
            })

        # Particles.
        particles = []
        for i, p_cfg in enumerate(sim.particles):
            bone_index = sim.resolve_bone_index(
                p_cfg.bone_name, particle_index=i
            )
            if bone_index is None:
                raise RuntimeError(
                    f"particle {i} references unresolved MetaRig bone "
                    f"'{p_cfg.bone_name}'"
                )
            proj = _PARTICLE_PROJ_TYPE_MAP.get(
                getattr(p_cfg, 'dyng_projection_type', 'DISABLED'), 0
            )
            particles.append({
                'bone_idx': int(bone_index),
                'node_idx': int(sim._particle_node_idx[i]),
                'mass': float(max(0.001, p_cfg.mass)),
                'damping': float(p_cfg.damping),
                'pull_force': float(p_cfg.pull_force),
                'capsule_radius': float(p_cfg.capsule_radius),
                'capsule_height': float(p_cfg.capsule_height),
                'capsule_axis_ls': sim.col_axis_ls[i].tolist(),
                'proj_type': proj,
                'is_pinned': bool(p_cfg.is_pinned),
                'active': True,
            })

        # Links. compile_dyng_links populates sim.link_idx_a/_b/_types/_lower/
        # _upper/_rest/_look_axes when there are any; absent or None otherwise.
        links = []
        link_idx_a = getattr(sim, 'link_idx_a', None)
        if link_idx_a is not None:
            for li in range(len(link_idx_a)):
                links.append({
                    'idx_a': int(sim.link_idx_a[li]),
                    'idx_b': int(sim.link_idx_b[li]),
                    'link_type': int(sim.link_types[li]),
                    'lower_ratio': float(sim.link_lower[li]),
                    'upper_ratio': float(sim.link_upper[li]),
                    'rest_distance': float(sim.link_rest[li]),
                    'look_at_axis': sim.link_look_axes[li].tolist(),
                })

        # Ellipsoids. _compile_ellipsoids in constraints.py populates these.
        ellipsoids = []
        ell_idx = getattr(sim, 'ell_idx', None)
        if ell_idx is not None:
            for ei in range(len(ell_idx)):
                ellipsoids.append({
                    'particle_idx': int(sim.ell_idx[ei]),
                    'target_bone_idx': int(sim.ell_centers[ei]),
                    'scale1': float(sim.ell_s1[ei]),
                    'scale2': float(sim.ell_s2[ei]),
                    'radius': float(sim.ell_radii[ei]),
                    'xform_ls': _matrix_to_flat(sim.ell_xform_ls[ei]),
                })

        # Cones (pendulum constraints).
        cones = []
        cone_idx = getattr(sim, 'cone_idx', None)
        if cone_idx is not None:
            for ci in range(len(cone_idx)):
                # Recover half-aperture from precomputed cosine. cone_cos is
                # cos(half_aperture); we invert via acos to feed the C++ side
                # which precomputes its own trig.
                cos_half = float(sim.cone_cos[ci])
                cos_half = max(-1.0, min(1.0, cos_half))
                half_aperture_rad = float(np.arccos(cos_half))

                cones.append({
                    'particle_idx': int(sim.cone_idx[ci]),
                    'attach_bone_idx': int(sim.cone_attach[ci]),
                    'constraint_type': int(sim.cone_type[ci]),
                    'half_aperture_rad': half_aperture_rad,
                    'projection_type': int(sim.cone_proj_type[ci]),
                    'collision_radius': float(sim.cone_col_radius[ci]),
                    'collision_height': float(sim.cone_col_height[ci]),
                    'xform_ls': _matrix_to_flat(sim.cone_xform_ls[ci]),
                })

        # Collision shapes. col_shapes is a list of dicts populated by
        # compile_collision_shapes; we re-marshal each.
        collision_shapes = []
        for shape in getattr(sim, 'col_shapes', []):
            bone_name = shape['bone_name']
            bone_index = sim.resolve_bone_index(bone_name)
            if bone_index is None:
                raise RuntimeError(
                    f"collision shape references unresolved MetaRig bone "
                    f"'{bone_name}'"
                )
            collision_shapes.append({
                'bone_idx': int(bone_index),
                'extents': shape['extents'].tolist(),
                'corner_radius': float(shape['radius']),
                'xform_ls': _matrix_to_flat(shape['ls_mat']),
            })

        return {
            'num_tracked_bones': num_tracked_bones,
            'nodes': nodes,
            'particles': particles,
            'links': links,
            'ellipsoids': ellipsoids,
            'cones': cones,
            'collision_shapes': collision_shapes,
        }

    # ------------------------------------------------------------------ properties

    @property
    def is_compiled(self):
        return self._compiled

    @property
    def native(self):
        return self._solver

    @property
    def num_tracked_bones(self):
        return self._num_tracked_bones
