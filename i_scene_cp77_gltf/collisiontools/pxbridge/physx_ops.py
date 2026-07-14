import bpy
import math
import base64
from math import inf
from mathutils import Matrix, Vector, Quaternion, Euler
from bpy_extras.view3d_utils import region_2d_to_vector_3d, region_2d_to_origin_3d
from . import physx_utils, viz

FABRIC_PRESETS = {
    'COTTON': {
        'mass': 1.0, 'friction': 0.5, 'drag': 0.02, 'damping': 0.12,
        'linear_drag': 0.05, 'solver_frequency': 280.0, 'stiffness_frequency': 120.0,
        'tether_scale': 1.0, 'tether_stiffness': 1.0, 'self_collision_distance': 0.004,
        'self_collision_stiffness': 0.5,
    },
    'DENIM': {
        'mass': 1.8, 'friction': 0.6, 'drag': 0.04, 'damping': 0.2,
        'linear_drag': 0.08, 'solver_frequency': 300.0, 'stiffness_frequency': 160.0,
        'tether_scale': 0.8, 'tether_stiffness': 1.0, 'self_collision_distance': 0.006,
        'self_collision_stiffness': 0.7,
    },
    'LEATHER': {
        'mass': 2.5, 'friction': 0.6, 'drag': 0.05, 'damping': 0.35,
        'linear_drag': 0.12, 'solver_frequency': 300.0, 'stiffness_frequency': 180.0,
        'tether_scale': 0.65, 'tether_stiffness': 1.0, 'self_collision_distance': 0.007,
        'self_collision_stiffness': 0.75,
    },
    'SILK': {
        'mass': 0.45, 'friction': 0.35, 'drag': 0.015, 'damping': 0.06,
        'linear_drag': 0.02, 'solver_frequency': 260.0, 'stiffness_frequency': 80.0,
        'tether_scale': 1.2, 'tether_stiffness': 0.85, 'self_collision_distance': 0.003,
        'self_collision_stiffness': 0.35,
    },
    'NYLON': {
        'mass': 0.65, 'friction': 0.4, 'drag': 0.015, 'damping': 0.08,
        'linear_drag': 0.025, 'solver_frequency': 270.0, 'stiffness_frequency': 100.0,
        'tether_scale': 1.0, 'tether_stiffness': 0.9, 'self_collision_distance': 0.003,
        'self_collision_stiffness': 0.4,
    },
    'RUBBER': {
        'mass': 1.9, 'friction': 0.6, 'drag': 0.04, 'damping': 0.3,
        'linear_drag': 0.1, 'solver_frequency': 300.0, 'stiffness_frequency': 160.0,
        'tether_scale': 0.9, 'tether_stiffness': 0.85, 'self_collision_distance': 0.006,
        'self_collision_stiffness': 0.65,
    },
}

QUALITY_MULTIPLIERS = {
    'DRAFT': {'solver_frequency': 0.65, 'stiffness_frequency': 0.75},
    'PREVIEW': {'solver_frequency': 1.0, 'stiffness_frequency': 1.0},
    'FINAL': {'solver_frequency': 1.2, 'stiffness_frequency': 1.15},
}


def _cloth_setting(obj, name, fallback=None):
    cloth = getattr(obj, "cp77_cloth", None)
    if not cloth:
        return fallback
    preset_name = getattr(cloth, "fabric_preset", 'CUSTOM')
    if preset_name != 'CUSTOM' and preset_name in FABRIC_PRESETS and name in FABRIC_PRESETS[preset_name]:
        value = FABRIC_PRESETS[preset_name][name]
    else:
        value = getattr(cloth, name, fallback)

    quality = getattr(cloth, "quality_preset", 'PREVIEW')
    multiplier = QUALITY_MULTIPLIERS.get(quality, {}).get(name, 1.0)
    if value is None:
        return fallback
    return float(value) * float(multiplier)


def _set_cloth_state(obj, state, message=""):
    cloth = getattr(obj, "cp77_cloth", None)
    if not cloth:
        return
    if hasattr(cloth, "workflow_state"):
        cloth.workflow_state = state
    if message:
        cloth.validation_status = message


def _cloth_frame_matrix(obj):
    loc = obj.matrix_world.to_translation()
    rot = obj.matrix_world.to_quaternion()
    return Matrix.Translation(loc) @ rot.to_matrix().to_4x4()


def _cloth_pose(obj):
    loc = obj.matrix_world.to_translation()
    quat = obj.matrix_world.to_quaternion()
    return [loc.x, loc.y, loc.z, quat.x, quat.y, quat.z, quat.w]


def _cloth_local_gravity(obj, gravity):
    q = obj.matrix_world.to_quaternion()
    g = q.inverted() @ Vector((gravity[0], gravity[1], gravity[2]))
    return [g.x, g.y, g.z]


def _iter_cloth_objects(context):
    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        cloth = getattr(obj, "cp77_cloth", None)
        if cloth and cloth.enabled:
            yield obj


def _iter_active_cloths(context):
    for obj in _iter_cloth_objects(context):
        handle_str = getattr(obj, "cp77_cloth_handle", "-1")
        if handle_str in {"", "0", "-1"}:
            continue
        try:
            yield obj, int(handle_str)
        except ValueError:
            continue


def _disable_live_deform_modifiers(obj):
    disabled = []
    for mod in obj.modifiers:
        if mod.type in {'ARMATURE', 'LATTICE', 'MESH_DEFORM', 'SURFACE_DEFORM', 'SHRINKWRAP', 'CLOTH'} and mod.show_viewport:
            disabled.append(mod.name)
            mod.show_viewport = False
    if disabled:
        obj["pxbridge_disabled_cloth_modifiers"] = ";".join(disabled)


def _get_cloth_mesh_data(obj):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    obj_eval = obj.evaluated_get(depsgraph)
    mesh = obj_eval.to_mesh()
    try:
        if len(mesh.vertices) != len(obj.data.vertices):
            raise ValueError(f"{obj.name}: cloth simulation requires modifiers that preserve vertex count")

        verts = [0.0] * (len(mesh.vertices) * 3)
        mesh.vertices.foreach_get("co", verts)

        # Seed the editable mesh with the evaluated pose once, then disable live
        # deformers so the simulation is not applied through the armature twice.
        obj.data.vertices.foreach_set("co", verts)
        obj.data.update()
    finally:
        obj_eval.to_mesh_clear()

    _disable_live_deform_modifiers(obj)

    mesh_data = obj.data
    mesh_data.calc_loop_triangles()
    indices = [0] * (len(mesh_data.loop_triangles) * 3)
    mesh_data.loop_triangles.foreach_get("vertices", indices)
    return verts, indices


def _build_inv_masses(obj, vertex_count):
    mass = max(_cloth_setting(obj, 'mass', 1.0), 0.001)
    inv_masses = [1.0 / mass] * vertex_count
    pinned = 0

    cloth = obj.cp77_cloth
    threshold = float(getattr(cloth, "pin_weight_threshold", 0.5))
    vg_name = cloth.pin_vg
    if vg_name and vg_name in obj.vertex_groups:
        vg = obj.vertex_groups[vg_name]
        for v in obj.data.vertices:
            if v.index >= vertex_count:
                continue
            for g in v.groups:
                if g.group == vg.index and g.weight >= threshold:
                    inv_masses[v.index] = 0.0
                    pinned += 1
                    break

    if pinned == 0 and vertex_count and getattr(cloth, "auto_pin_fallback", False):
        coords = [obj.data.vertices[i].co for i in range(min(vertex_count, len(obj.data.vertices)))]
        if coords:
            z_min = min(v.z for v in coords)
            z_max = max(v.z for v in coords)
            z_span = z_max - z_min
            # Only auto-pin a raised band when the garment has real vertical extent.
            # Flat test cloth must be allowed to drape freely instead of silently
            # pinning every particle, which can destabilize NvCloth fabric cooking.
            if z_span > 1.0e-5:
                threshold_z = z_max - max(z_span * 0.05, 1.0e-4)
                for i, co in enumerate(coords):
                    if co.z >= threshold_z:
                        inv_masses[i] = 0.0
                        pinned += 1

    if hasattr(cloth, "last_pinned_count"):
        cloth.last_pinned_count = pinned
    return inv_masses


def _vertex_group_weight(obj, vg_name, index):
    if not vg_name or vg_name not in obj.vertex_groups or index >= len(obj.data.vertices):
        return 0.0
    group_index = obj.vertex_groups[vg_name].index
    for g in obj.data.vertices[index].groups:
        if g.group == group_index:
            return max(0.0, min(1.0, float(g.weight)))
    return 0.0


def _build_motion_constraints(obj, verts, vertex_count):
    cloth = obj.cp77_cloth
    source = getattr(cloth, "motion_constraint_source", 'NONE')
    if source == 'NONE' or vertex_count <= 0:
        cloth.last_motion_constraint_count = 0
        return []

    if source == 'PIN_GROUP':
        group_name = cloth.pin_vg
    elif source == 'MOTION_GROUP':
        group_name = cloth.motion_constraint_vg
    else:
        group_name = ""

    base_radius = max(float(getattr(cloth, "motion_constraint_radius", 0.15)), 0.0)
    min_radius = max(float(getattr(cloth, "motion_constraint_min_radius", 0.0)), 0.0)
    inactive_radius = 1.0e6
    constraints = []
    active = 0

    for i in range(vertex_count):
        x, y, z = verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2]
        if source == 'ALL':
            weight = 1.0
        else:
            weight = _vertex_group_weight(obj, group_name, i)

        if weight > 0.001:
            radius = max(min_radius, base_radius * (1.0 - weight))
            active += 1
        else:
            radius = inactive_radius
        constraints.extend([x, y, z, radius])

    cloth.last_motion_constraint_count = active
    return constraints if active else []


def _build_separation_constraints(obj, verts, vertex_count):
    cloth = obj.cp77_cloth
    source = getattr(cloth, "separation_constraint_source", 'NONE')
    if source == 'NONE' or vertex_count <= 0:
        cloth.last_separation_constraint_count = 0
        return []

    group_name = getattr(cloth, "separation_constraint_vg", "")
    radius = max(float(getattr(cloth, "separation_constraint_radius", 0.05)), 0.0)
    offset = float(getattr(cloth, "separation_constraint_offset", 0.0))
    constraints = []
    active = 0

    normals = []
    try:
        for vert in obj.data.vertices:
            normals.append(vert.normal.copy())
    except Exception:
        normals = []

    for i in range(vertex_count):
        x, y, z = verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2]
        weight = _vertex_group_weight(obj, group_name, i)
        if source == 'SEPARATION_GROUP' and weight > 0.001:
            if i < len(normals):
                n = normals[i]
                x += n.x * offset
                y += n.y * offset
                z += n.z * offset
            constraints.extend([x, y, z, radius * weight])
            active += 1
        else:
            constraints.extend([x, y, z, 0.0])

    cloth.last_separation_constraint_count = active
    return constraints if active else []


def _apply_native_constraints(obj, cloth_handle, verts, vertex_count, _bridge):
    motion = _build_motion_constraints(obj, verts, vertex_count)
    if motion and hasattr(_bridge, "nvcloth_set_motion_constraints"):
        _bridge.nvcloth_set_motion_constraints(cloth_handle, motion)
        if hasattr(_bridge, "nvcloth_set_motion_constraint_scale_bias"):
            _bridge.nvcloth_set_motion_constraint_scale_bias(
                cloth_handle,
                float(getattr(obj.cp77_cloth, "motion_constraint_scale", 1.0)),
                float(getattr(obj.cp77_cloth, "motion_constraint_bias", 0.0)),
            )
        if hasattr(_bridge, "nvcloth_set_motion_constraint_stiffness"):
            _bridge.nvcloth_set_motion_constraint_stiffness(
                cloth_handle, float(getattr(obj.cp77_cloth, "motion_constraint_stiffness", 1.0))
            )
    elif hasattr(_bridge, "nvcloth_clear_motion_constraints"):
        _bridge.nvcloth_clear_motion_constraints(cloth_handle)
        obj.cp77_cloth.last_motion_constraint_count = 0

    separation = _build_separation_constraints(obj, verts, vertex_count)
    if separation and hasattr(_bridge, "nvcloth_set_separation_constraints"):
        _bridge.nvcloth_set_separation_constraints(cloth_handle, separation)
    elif hasattr(_bridge, "nvcloth_clear_separation_constraints"):
        _bridge.nvcloth_clear_separation_constraints(cloth_handle)
        obj.cp77_cloth.last_separation_constraint_count = 0


def _cloth_avatar_armatures(cloth_obj, context):
    cloth = getattr(cloth_obj, "cp77_cloth", None)
    avatar = getattr(cloth, "avatar_armature", None) if cloth else None
    if avatar and avatar.type == 'ARMATURE':
        return [avatar]
    return [obj for obj in context.scene.objects if obj.type == 'ARMATURE' and hasattr(obj, "cp77_cloth_colliders")]


def _avatar_region_inflate(arm_obj, region):
    profile = getattr(arm_obj, "cp77_avatar", None)
    if not profile or not getattr(profile, "enabled", True):
        return 0.0
    if region == 'TORSO':
        return float(getattr(profile, "torso_inflate", 0.0))
    if region == 'PELVIS':
        return float(getattr(profile, "pelvis_inflate", 0.0))
    if region == 'ARM':
        return float(getattr(profile, "arm_inflate", 0.0))
    if region == 'LEG':
        return float(getattr(profile, "leg_inflate", 0.0))
    if region == 'HEAD':
        return float(getattr(profile, "head_inflate", 0.0))
    return 0.0


def _avatar_collider_radius(arm_obj, col, garment_inflate):
    profile = getattr(arm_obj, "cp77_avatar", None)
    avatar_inflate = float(getattr(profile, "global_inflate", 0.0)) if profile else 0.0
    region_inflate = _avatar_region_inflate(arm_obj, getattr(col, "region", 'CUSTOM'))
    return max(abs(float(col.radius)) + garment_inflate + avatar_inflate + region_inflate, 1.0e-4)


def _avatar_body_mesh_for_armature(arm_obj, context, auto_detect=False):
    profile = getattr(arm_obj, "cp77_avatar", None)
    if profile and getattr(profile, "body_mesh", None) and profile.body_mesh.type == 'MESH':
        return profile.body_mesh

    if not auto_detect:
        return None

    for obj in context.scene.objects:
        if obj.type != 'MESH':
            continue
        for mod in obj.modifiers:
            if mod.type == 'ARMATURE' and mod.object == arm_obj:
                if profile:
                    profile.body_mesh = obj
                return obj
        if obj.parent == arm_obj:
            if profile:
                profile.body_mesh = obj
            return obj
    return None


def _build_avatar_mesh_collision(cloth_obj, context):
    cloth = getattr(cloth_obj, "cp77_cloth", None)
    if not cloth:
        return [], [], 0

    cloth_inv = _cloth_frame_matrix(cloth_obj).inverted_safe()
    all_vertices = []
    all_indices = []
    tri_total = 0

    for arm_obj in _cloth_avatar_armatures(cloth_obj, context):
        profile = getattr(arm_obj, "cp77_avatar", None)
        if not profile or not getattr(profile, "enabled", True):
            continue
        if not getattr(profile, "use_mesh_collision", False):
            continue

        mesh_obj = _avatar_body_mesh_for_armature(arm_obj, context)
        if not mesh_obj or mesh_obj == cloth_obj or mesh_obj.type != 'MESH':
            continue

        max_tris = max(64, int(getattr(profile, "mesh_collision_max_tris", 1500)))
        depsgraph = context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        eval_mesh = eval_obj.to_mesh()
        try:
            eval_mesh.calc_loop_triangles()
            tris = list(eval_mesh.loop_triangles)
            tri_count = len(tris)
            if tri_count == 0:
                continue

            stride = max(1, math.ceil(tri_count / max_tris))
            vert_offset = len(all_vertices) // 3
            mw = eval_obj.matrix_world
            for v in eval_mesh.vertices:
                local = cloth_inv @ (mw @ v.co)
                all_vertices.extend([local.x, local.y, local.z])

            for tri in tris[::stride]:
                ids = tri.vertices
                all_indices.extend([vert_offset + ids[0], vert_offset + ids[1], vert_offset + ids[2]])
                tri_total += 1
        finally:
            eval_obj.to_mesh_clear()

    return all_vertices, all_indices, tri_total


def _avatar_uses_primitive_collision(cloth_obj, context):
    for arm_obj in _cloth_avatar_armatures(cloth_obj, context):
        profile = getattr(arm_obj, "cp77_avatar", None)
        if profile and getattr(profile, "enabled", True):
            if getattr(profile, "use_primitive_collision", False):
                return True
    return False


def validate_cloth_object(obj, context):
    errors = []
    warnings = []
    stats = {"vertices": 0, "triangles": 0, "pinned": 0, "colliders": 0}

    if not obj or obj.type != 'MESH':
        return ["Active garment must be a mesh"], warnings, stats

    mesh = obj.data
    stats["vertices"] = len(mesh.vertices)
    mesh.calc_loop_triangles()
    stats["triangles"] = len(mesh.loop_triangles)

    if stats["vertices"] < 3:
        errors.append(f"{obj.name}: garment mesh has fewer than 3 vertices")
    if stats["triangles"] == 0:
        errors.append(f"{obj.name}: garment mesh has no triangulated faces")

    scale = obj.matrix_world.to_scale()
    if min(abs(scale.x), abs(scale.y), abs(scale.z)) < 1.0e-6:
        errors.append(f"{obj.name}: object scale contains a zero axis")
    elif max(abs(scale.x), abs(scale.y), abs(scale.z)) / max(min(abs(scale.x), abs(scale.y), abs(scale.z)), 1.0e-6) > 1.25:
        warnings.append(f"{obj.name}: non-uniform scale can make cloth/collider spacing harder to tune")

    cloth = obj.cp77_cloth
    vg_name = cloth.pin_vg
    if vg_name and vg_name in obj.vertex_groups:
        vg = obj.vertex_groups[vg_name]
        for v in mesh.vertices:
            for g in v.groups:
                if g.group == vg.index and g.weight >= getattr(cloth, "pin_weight_threshold", 0.5):
                    stats["pinned"] += 1
                    break
    elif not getattr(cloth, "auto_pin_fallback", True):
        warnings.append(f"{obj.name}: pin group '{vg_name}' does not exist")

    avatar_armatures = _cloth_avatar_armatures(obj, context)
    mesh_vertices, mesh_indices, mesh_tris = _build_avatar_mesh_collision(obj, context)
    stats["avatar_mesh_tris"] = mesh_tris
    if mesh_tris > 0:
        stats["colliders"] += mesh_tris

    if _avatar_uses_primitive_collision(obj, context) or mesh_tris == 0:
        for scene_obj in avatar_armatures:
            if hasattr(scene_obj, "cp77_cloth_colliders"):
                stats["colliders"] += len([c for c in scene_obj.cp77_cloth_colliders if getattr(c, "enabled", True)])

    if stats["colliders"] == 0:
        warnings.append("No avatar mesh or enabled avatar colliders were found for this garment")
    if not cloth.avatar_armature and len(avatar_armatures) > 1:
        warnings.append("Multiple avatar profiles are present; assign one explicitly to this garment")

    if stats["pinned"] == 0 and not getattr(cloth, "auto_pin_fallback", True):
        warnings.append(f"{obj.name}: no pinned vertices were found")

    return errors, warnings, stats


def write_cloth_validation(obj, errors, warnings, stats):
    cloth = obj.cp77_cloth
    cloth.last_particle_count = int(stats.get("vertices", 0))
    cloth.last_triangle_count = int(stats.get("triangles", 0))
    cloth.last_pinned_count = int(stats.get("pinned", 0))
    cloth.last_collider_count = int(stats.get("colliders", 0))
    if errors:
        cloth.workflow_state = 'ERROR'
        cloth.validation_status = "; ".join(errors[:3])
        cloth.validation_errors = "\n".join(errors + warnings)
    else:
        cloth.workflow_state = 'READY'
        suffix = f" ({len(warnings)} warning{'s' if len(warnings) != 1 else ''})" if warnings else ""
        cloth.validation_status = f"Ready: {stats['vertices']} verts, {stats['triangles']} tris, {stats['pinned']} pinned, {stats['colliders']} colliders{suffix}"
        cloth.validation_errors = "\n".join(warnings)


def update_cloth_colliders(cloth_obj, cloth_handle_int, context, _bridge, init_capsules=False):
    cloth_colliders = []
    for obj in _cloth_avatar_armatures(cloth_obj, context):
        if obj.type == 'ARMATURE' and hasattr(obj, "cp77_cloth_colliders"):
            profile = getattr(obj, "cp77_avatar", None)
            if profile and not getattr(profile, "enabled", True):
                continue
            for col in obj.cp77_cloth_colliders:
                if getattr(col, "enabled", True):
                    cloth_colliders.append((obj, col))

    cloth_inv = _cloth_frame_matrix(cloth_obj).inverted_safe()
    spheres_data = []
    sphere_idx_map = {}
    capsule_pairs = []
    max_spheres = 32
    inflate = max(float(getattr(cloth_obj.cp77_cloth, "collision_inflate", 0.0)), 0.0)

    def set_radius(idx, radius):
        spheres_data[idx * 4 + 3] = max(spheres_data[idx * 4 + 3], max(abs(radius), 1.0e-4))

    def add_sphere_at(key, pos_local, radius):
        if key in sphere_idx_map:
            idx = sphere_idx_map[key]
            set_radius(idx, radius)
            return idx
        if len(sphere_idx_map) >= max_spheres:
            return None

        idx = len(sphere_idx_map)
        sphere_idx_map[key] = idx
        spheres_data.extend([
            pos_local.x, pos_local.y, pos_local.z, max(abs(radius), 1.0e-4)
        ])
        return idx

    def add_bone_sphere(arm_obj, bone_name, radius):
        if not bone_name or bone_name not in arm_obj.pose.bones:
            return None
        pos_world = physx_utils.get_bone_world_matrix(arm_obj, bone_name).to_translation()
        pos_local = cloth_inv @ pos_world
        return add_sphere_at(f"bone:{arm_obj.name}:{bone_name}", pos_local, radius)

    for arm_obj, col in cloth_colliders:
        if col.collider_type == 'SPHERE':
            add_bone_sphere(arm_obj, col.bone, _avatar_collider_radius(arm_obj, col, inflate))

    for arm_obj, col in cloth_colliders:
        if col.collider_type != 'CAPSULE':
            continue
        radius = _avatar_collider_radius(arm_obj, col, inflate)
        a = add_bone_sphere(arm_obj, col.bone, radius)
        b = add_bone_sphere(arm_obj, col.target_bone, radius)
        if a is None or b is None or a == b:
            continue
        capsule_pairs.extend([a, b])

    if hasattr(_bridge, "nvcloth_enable_continuous_collision"):
        _bridge.nvcloth_enable_continuous_collision(cloth_handle_int, bool(getattr(cloth_obj.cp77_cloth, "continuous_collision", True)))
    if hasattr(_bridge, "nvcloth_set_collision_mass_scale"):
        _bridge.nvcloth_set_collision_mass_scale(cloth_handle_int, float(getattr(cloth_obj.cp77_cloth, "collision_mass_scale", 3.0)))

    _bridge.nvcloth_set_spheres(cloth_handle_int, spheres_data)
    _bridge.nvcloth_set_capsules(cloth_handle_int, capsule_pairs)

    counts = _bridge.nvcloth_get_collider_counts(cloth_handle_int) if hasattr(_bridge, "nvcloth_get_collider_counts") else {}
    cloth_obj["pxbridge_cloth_sphere_count"] = int(counts.get("spheres", len(spheres_data) // 4)) if hasattr(counts, "get") else len(spheres_data) // 4
    cloth_obj["pxbridge_cloth_capsule_count"] = int(counts.get("capsules", len(capsule_pairs) // 2)) if hasattr(counts, "get") else len(capsule_pairs) // 2
    cloth_obj["pxbridge_cloth_capsule_slot_count"] = int(counts.get("capsule_slots", len(capsule_pairs) // 2)) if hasattr(counts, "get") else len(capsule_pairs) // 2
    cloth_obj["pxbridge_cloth_virtual_capsule_count"] = 0
    cloth_obj["pxbridge_cloth_avatar_mesh_triangle_count"] = 0
    cloth_obj["pxbridge_cloth_capsule_mode"] = "native_capsules_ccd"


def _prepare_cloth_step(context, _bridge):
    g = context.scene.physx.gravity
    for obj, handle in _iter_active_cloths(context):
        pose = _cloth_pose(obj)
        _bridge.nvcloth_set_translation(handle, pose[:3])
        _bridge.nvcloth_set_rotation(handle, pose[3:])
        _bridge.nvcloth_set_gravity(handle, _cloth_local_gravity(obj, g))
        update_cloth_colliders(obj, handle, context, _bridge)


def _apply_cloth_particles(context, _bridge):
    for obj, handle in _iter_active_cloths(context):
        particles = _bridge.nvcloth_get_particles(handle)
        if particles is None or len(particles) == 0:
            continue
        count = min(len(obj.data.vertices), len(particles))
        for i in range(count):
            x = float(particles[i][0])
            y = float(particles[i][1])
            z = float(particles[i][2])
            if math.isfinite(x) and math.isfinite(y) and math.isfinite(z):
                obj.data.vertices[i].co = (x, y, z)
        obj.data.update()
        obj.update_tag(refresh={'DATA'})


def _step_bridge(context, _bridge, dt):
    _prepare_cloth_step(context, _bridge)
    _bridge.start_step(dt)
    ok = _bridge.fetch_results(True)
    _apply_cloth_particles(context, _bridge)
    return ok


class PHYSX_OT_init_scene(bpy.types.Operator):
    bl_idname = "physx.init_scene"
    bl_label = "Initialize Scene"

    add_ground = bpy.props.BoolProperty(name="Add Ground Plane", default=True)
    ground = None

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if _bridge.init():
                context.scene.physx.is_initialized = True
                g = context.scene.physx.gravity
                _bridge.set_gravity(g[0], g[1], g[2])
                self.report({'INFO'}, "PhysX Initialized")
                if self.add_ground:
                    ground_obj = physx_utils.add_ground_plane()
                    already_added = False
                    for item in context.scene.physx.actors:
                        if item.obj_ref == ground_obj:
                            already_added = True
                            break

                    if not already_added:
                        item = context.scene.physx.actors.add()
                        item.obj_ref = ground_obj
                        px = ground_obj.physx
                        px.actor_type = 'STATIC'
                        if len(px.shapes) == 0:
                            shp = px.shapes.add()
                            shp.name = "GroundBox"
                            shp.shape_type = 'BOX'
                            dims = ground_obj.dimensions
                            shp.dim_x = dims.x / 2.0
                            shp.dim_y = dims.y / 2.0
                            shp.dim_z = dims.z / 2.0
            else:
                self.report({'ERROR'}, "Init Failed")
        except ImportError:
            self.report({'ERROR'}, "DLL Missing")
        return {'FINISHED'}


class PHYSX_OT_validate_scene(bpy.types.Operator):
    bl_idname = "physx.validate_scene"
    bl_label = "Validate Scene"

    def execute(self, context):
        px_s = context.scene.physx
        errors = []
        for item in px_s.actors:
            obj = item.obj_ref
            if not obj: continue
            px = obj.physx
            for shape in px.shapes:
                if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD') and not shape.cooked_data:
                    errors.append(f"{obj.name}: {shape.name} not cooked")
        if errors:
            self.report({'ERROR'}, "Errors: " + "; ".join(errors))
            return {'CANCELLED'}
        self.report({'INFO'}, "Scene Valid")
        return {'FINISHED'}


class PHYSX_OT_build_scene(bpy.types.Operator):
    bl_idname = "physx.build_scene"
    bl_label = "Build PhysX Scene"

    def execute(self, context):
        bpy.ops.physx.validate_scene()
        try:
            from . import pxbridge as _bridge
            _bridge.reset()
            g = context.scene.physx.gravity
            _bridge.set_gravity(g[0], g[1], g[2])
            count = 0

            for item in context.scene.physx.actors:
                obj = item.obj_ref
                if not obj or obj.physx.actor_type == 'NONE': continue
                px = obj.physx

                shapes_list = []
                for shape in px.shapes:
                    raw = ""
                    if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD'):
                        if not shape.cooked_data: continue
                        raw = base64.b64decode(shape.cooked_data.encode('ascii'))

                    mat_data = physx_utils.get_mat_data(shape.physics_material)
                    q = shape.local_rot
                    l = shape.local_pos
                    px_quat = [q[1], q[2], q[3], q[0]]

                    w0 = physx_utils.bits_to_int(shape.filter_group)
                    w1 = physx_utils.bits_to_int(shape.filter_mask)
                    w2 = physx_utils.bits_to_int(shape.filter_query)
                    w3 = 0

                    shapes_list.append(
                            {
                                "type": shape.shape_type,
                                "data": raw,
                                "dims": [shape.dim_x, shape.dim_y, shape.dim_z],
                                "pos": [l[0], l[1], l[2]],
                                "rot": px_quat,
                                "mat": mat_data,
                                "filter": [w0, w1, w2, w3]
                                }
                            )

                if not shapes_list: continue
                loc, quat = physx_utils.get_actor_world_transform(item)
                actor_pose = [loc.x, loc.y, loc.z, quat.x, quat.y, quat.z, quat.w]
                com = [px.com_offset[0], px.com_offset[1], px.com_offset[2]]
                inert = [px.inertia[0], px.inertia[1], px.inertia[2]]

                handle = _bridge.create_actor(px.actor_type, actor_pose, shapes_list, px.mass, com, inert)
                item.actor_handle = str(handle)
                count += 1

            if hasattr(_bridge, "nvcloth_is_initialized"):
                _bridge.nvcloth_shutdown()
                _bridge.nvcloth_init(False)

                for obj in _iter_cloth_objects(context):
                    errors, warnings, stats = validate_cloth_object(obj, context)
                    write_cloth_validation(obj, errors, warnings, stats)
                    if errors:
                        raise RuntimeError("; ".join(errors))

                    verts, indices = _get_cloth_mesh_data(obj)
                    vertex_count = len(verts) // 3
                    if vertex_count == 0 or len(indices) < 3:
                        raise RuntimeError(f"{obj.name}: cloth mesh has no triangle topology")

                    inv_masses = _build_inv_masses(obj, vertex_count)
                    fixed_count = sum(1 for m in inv_masses if m <= 0.0)
                    if fixed_count >= vertex_count:
                        raise RuntimeError(f"{obj.name}: all cloth particles are pinned; unpin part of the garment before preparing")

                    g = context.scene.physx.gravity
                    local_g = _cloth_local_gravity(obj, g)
                    use_tethers = 0 < fixed_count < vertex_count
                    fabric_data = _bridge.nvcloth_cook_fabric(verts, indices, inv_masses, local_g, use_tethers)
                    if not fabric_data:
                        raise RuntimeError(f"NvCloth failed to cook fabric for {obj.name}")

                    fabric_handle = _bridge.nvcloth_load_fabric(fabric_data)
                    if not fabric_handle:
                        raise RuntimeError(f"NvCloth failed to load fabric for {obj.name}")

                    packed_particles = []
                    for i in range(vertex_count):
                        packed_particles.extend([verts[i * 3], verts[i * 3 + 1], verts[i * 3 + 2], inv_masses[i]])

                    cloth_handle = _bridge.nvcloth_create_cloth(fabric_handle, packed_particles, _cloth_pose(obj))
                    if not cloth_handle:
                        raise RuntimeError(f"NvCloth failed to create cloth for {obj.name}")
                    obj.cp77_cloth_handle = str(cloth_handle)

                    _bridge.nvcloth_set_particles(cloth_handle, packed_particles)
                    _bridge.nvcloth_set_inv_masses(cloth_handle, inv_masses)
                    _bridge.nvcloth_set_gravity(cloth_handle, local_g)
                    _bridge.nvcloth_set_solver_frequency(cloth_handle, _cloth_setting(obj, 'solver_frequency', 300.0))
                    if hasattr(_bridge, "nvcloth_set_stiffness_frequency"):
                        _bridge.nvcloth_set_stiffness_frequency(cloth_handle, _cloth_setting(obj, 'stiffness_frequency', 120.0))
                    if hasattr(_bridge, "nvcloth_set_damping"):
                        d = _cloth_setting(obj, 'damping', 0.12)
                        _bridge.nvcloth_set_damping(cloth_handle, [d, d, d])
                    if hasattr(_bridge, "nvcloth_set_linear_drag"):
                        ld = _cloth_setting(obj, 'linear_drag', 0.05)
                        _bridge.nvcloth_set_linear_drag(cloth_handle, [ld, ld, ld])
                    if hasattr(_bridge, "nvcloth_set_tether_constraint_scale"):
                        _bridge.nvcloth_set_tether_constraint_scale(cloth_handle, _cloth_setting(obj, 'tether_scale', 1.0))
                    if hasattr(_bridge, "nvcloth_set_tether_constraint_stiffness"):
                        _bridge.nvcloth_set_tether_constraint_stiffness(cloth_handle, _cloth_setting(obj, 'tether_stiffness', 1.0))
                    if hasattr(_bridge, "nvcloth_set_self_collision_distance"):
                        _bridge.nvcloth_set_self_collision_distance(cloth_handle, _cloth_setting(obj, 'self_collision_distance', 0.0))
                    if hasattr(_bridge, "nvcloth_set_self_collision_stiffness"):
                        _bridge.nvcloth_set_self_collision_stiffness(cloth_handle, _cloth_setting(obj, 'self_collision_stiffness', 0.5))
                    _apply_native_constraints(obj, cloth_handle, verts, vertex_count, _bridge)
                    _bridge.nvcloth_set_friction(cloth_handle, _cloth_setting(obj, 'friction', 0.5))
                    if hasattr(_bridge, "nvcloth_enable_continuous_collision"):
                        _bridge.nvcloth_enable_continuous_collision(cloth_handle, bool(getattr(obj.cp77_cloth, "continuous_collision", True)))
                    if hasattr(_bridge, "nvcloth_set_collision_mass_scale"):
                        _bridge.nvcloth_set_collision_mass_scale(cloth_handle, float(getattr(obj.cp77_cloth, "collision_mass_scale", 3.0)))
                    _bridge.nvcloth_set_drag_coefficient(cloth_handle, _cloth_setting(obj, 'drag', 0.0))
                    if hasattr(_bridge, "nvcloth_clear_inertia"):
                        _bridge.nvcloth_clear_inertia(cloth_handle)
                    update_cloth_colliders(obj, int(cloth_handle), context, _bridge, init_capsules=True)
                    _set_cloth_state(obj, 'READY', f"Prepared {vertex_count} particles")

            context.scene.physx.active_actor_count = _bridge.get_actor_count()
            context.scene.physx.scene_built = True
            self.report({'INFO'}, f"Built {count} actors")
            return {'FINISHED'}
        except Exception as e:
            for obj in _iter_cloth_objects(context):
                _set_cloth_state(obj, 'ERROR', str(e))
            self.report({'ERROR'}, str(e))
            return {'CANCELLED'}


class PHYSX_OT_run_steps(bpy.types.Operator):
    bl_idname = "physx.run_steps"
    bl_label = "Step N"

    @classmethod
    def poll(cls, context):
        return context.scene.physx.is_initialized

    def execute(self, context):
        px_s = context.scene.physx
        if not px_s.is_initialized: return {'CANCELLED'}
        try:
            from . import pxbridge as _bridge
            dt = 1.0 / 60.0
            for _ in range(px_s.sim_steps):
                _step_bridge(context, _bridge, dt)
            poses = _bridge.get_active_poses()
            if poses:
                for item in px_s.actors:
                    h = item.actor_handle
                    if h in poses and item.obj_ref:
                        p = poses[h]
                        loc = Vector((p[0], p[1], p[2]))
                        quat = Quaternion((p[6], p[3], p[4], p[5]))
                        world_matrix = Matrix.Translation(loc) @ quat.to_matrix().to_4x4()
                        if item.use_bone_parent and item.parent_armature != "NONE" and item.target_bone != "NONE":
                            armature_obj = context.scene.objects.get(item.parent_armature)
                            if armature_obj:
                                physx_utils.set_bone_world_matrix(armature_obj, item.target_bone, world_matrix)
                        else:
                            item.obj_ref.matrix_world = world_matrix
            viz.invalidate_visualization_cache()
            for window in context.window_manager.windows:
                for area in window.screen.areas: area.tag_redraw()
            self.report({'INFO'}, f"Stepped {px_s.sim_steps}")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class PHYSX_OT_sim_step(bpy.types.Operator):
    bl_idname = "physx.sim_step"
    bl_label = "Run Simulation"
    _timer = None
    _cursor_handle = "0"
    cursor_radius: bpy.props.FloatProperty(name="Cursor Radius", default=1.0)

    @classmethod
    def poll(cls, context):
        px_s = context.scene.physx
        return px_s.is_initialized and not px_s.sim_running

    def invoke(self, context, event):
        if not context.scene.physx.scene_built:
            bpy.ops.physx.build_scene()
        context.scene.physx.sim_running = True
        for obj in _iter_active_cloths(context):
            _set_cloth_state(obj[0], 'SIMULATING', 'Simulation running')
        self._timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        px_s = context.scene.physx
        if not px_s.sim_running:
            return self.cancel(context)
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            return self.cancel(context)
        from . import pxbridge as _bridge

        # Manipulator
        if event.type == 'MOUSEMOVE':
            if context.region and context.region_data:
                vec = region_2d_to_vector_3d(
                        context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y)
                        )
                orig = region_2d_to_origin_3d(
                        context.region, context.region_data, (event.mouse_region_x, event.mouse_region_y)
                        )
                if abs(vec.z) > 0.0001:
                    t = -orig.z / vec.z
                    if t > 0:
                        pos = orig + vec * t
                        px_s.manipulator_pos = pos
                        if px_s.use_grab_mode:
                            if self._cursor_handle == "0":
                                target_preset_name = physx_utils.presets_lib._OVERRIDES.get(
                                        "All Collision Touch All", "World Dynamic"
                                        )
                                w0, w1, w2, w3 = 0, 0, 0, 0
                                if target_preset_name in physx_utils.presets_lib._RAW_PRESETS:
                                    data = physx_utils.presets_lib._RAW_PRESETS[target_preset_name]
                                    for name in data[0]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=False)
                                        if idx >= 0: w0 |= (1 << idx)
                                    for name in data[1]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=False)
                                        if idx >= 0: w1 |= (1 << idx)
                                    for name in data[2]:
                                        idx = physx_utils.presets_lib.get_layer_bit(name, is_query=True)
                                        if idx >= 0: w2 |= (1 << idx)

                                start_pose = [pos.x, pos.y, pos.z, 0, 0, 0, 1]
                                shape_def = {
                                    "type": "SPHERE", "data": "", "dims": [self.cursor_radius, 0, 0],
                                    "pos": [0, 0, 0], "rot": [0, 0, 0, 1], "mat": [0.5, 0.5, 0.5],
                                    "filter": [w0, w1, w2, w3]
                                    }
                                h = _bridge.create_actor(
                                        "KINEMATIC", start_pose, [shape_def], 1.0, [0, 0, 0], [1, 1, 1]
                                        )
                                self._cursor_handle = str(h)
                                px_s.manipulator_handle = str(h)
                            else:
                                bridge_pos = [pos.x, pos.y, pos.z]
                                bridge_rot = [0, 0, 0, 1]
                                try:
                                    _bridge.set_kinematic_target(int(self._cursor_handle), bridge_pos, bridge_rot)
                                except Exception:
                                    pass

        if event.type == 'TIMER':
            dt = 1.0 / 60.0
            _step_bridge(context, _bridge, dt)

            poses = _bridge.get_active_poses()
            for item in px_s.actors:
                h = item.actor_handle
                if h in poses and item.obj_ref:
                    p = poses[h]
                    loc = Vector((p[0], p[1], p[2]))
                    quat = Quaternion((p[6], p[3], p[4], p[5]))
                    world_matrix = Matrix.Translation(loc) @ quat.to_matrix().to_4x4()
                    if item.use_bone_parent and item.parent_armature != "NONE" and item.target_bone != "NONE":
                        armature_obj = context.scene.objects.get(item.parent_armature)
                        if armature_obj:
                            physx_utils.set_bone_world_matrix(armature_obj, item.target_bone, world_matrix)
                    else:
                        item.obj_ref.matrix_world = world_matrix

            # Force update
            viz.invalidate_visualization_cache()
            context.view_layer.update()
        return {'PASS_THROUGH'}

    def execute(self, context):
        return self.invoke(context, None)

    def cancel(self, context):
        context.scene.physx.sim_running = False
        for obj, _handle in _iter_active_cloths(context):
            _set_cloth_state(obj, 'PAUSED', 'Simulation paused')
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if self._cursor_handle != "0":
            from . import pxbridge as _bridge
            try:
                _bridge.remove_actor(int(self._cursor_handle))
            except:
                pass
            self._cursor_handle = "0"
            context.scene.physx.manipulator_handle = "0"
        return {'CANCELLED'}


class PHYSX_OT_stop_sim(bpy.types.Operator):
    bl_idname = "physx.stop_sim"
    bl_label = "Stop"

    def execute(self, context):
        context.scene.physx.sim_running = False
        for obj, _handle in _iter_active_cloths(context):
            _set_cloth_state(obj, 'PAUSED', 'Simulation paused')
        return {'FINISHED'}


class PHYSX_OT_apply_force(bpy.types.Operator):
    bl_idname = "physx.apply_force"
    bl_label = "Apply Force"

    def execute(self, context):
        px_s = context.scene.physx
        obj = context.active_object
        h = "0"
        for item in px_s.actors:
            if item.obj_ref == obj:
                h = item.actor_handle
                break
        if h == "0": return {'CANCELLED'}
        from . import pxbridge as _bridge
        f = px_s.force_value
        p = context.scene.cursor.location if px_s.use_force_pos else Vector((0, 0, 0))
        _bridge.apply_force(int(h), [f[0], f[1], f[2]], int(px_s.force_mode), px_s.use_force_pos, [p.x, p.y, p.z])
        return {'FINISHED'}


class PHYSX_OT_update_gravity(bpy.types.Operator):
    bl_idname = "physx.update_gravity"
    bl_label = "Update Gravity"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            g = context.scene.physx.gravity
            _bridge.set_gravity(g[0], g[1], g[2])
        except:
            pass
        return {'FINISHED'}


class PHYSX_OT_cook_mesh(bpy.types.Operator):
    bl_idname = "physx.cook_mesh";
    bl_label = "Cook"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            if not _bridge.init(): return {'CANCELLED'}
            obj = context.object
            shape = obj.physx.shapes[obj.physx.shape_index]
            if shape.shape_type == 'HEIGHTFIELD':
                mw = obj.matrix_world
                min_x = min_y = min_z = inf
                max_x = max_y = max_z = -inf
                for b in obj.bound_box:
                    x, y, z = mw @ Vector(b)
                    if x < min_x: min_x = x
                    if x > max_x: max_x = x
                    if y < min_y: min_y = y
                    if y > max_y: max_y = y
                    if z < min_z: min_z = z
                    if z > max_z: max_z = z
                rows = shape.hf_resolution
                cols = shape.hf_resolution
                if rows < 2 or cols < 2: raise ValueError("Resolution must be >= 2")
                step_x = (max_x - min_x) / (cols - 1)
                step_y = (max_y - min_y) / (rows - 1)
                verts, indices = physx_utils.get_raw_mesh_data(obj)
                loc = obj.matrix_world.to_translation()
                rot = obj.matrix_world.to_quaternion()
                transform = [loc.x, loc.y, loc.z, rot.x, rot.y, rot.z, rot.w]
                cooked = _bridge.cook_hf_from_mesh(
                        rows, cols, [min_x, min_y, min_z], [step_x, step_y], verts, indices, transform
                        )
            else:
                verts, indices = physx_utils.get_clean_mesh_data(obj, shape.shape_type, shape.vertex_limit)
                cooked = _bridge.cook_mesh(shape.shape_type, verts, indices, shape.vertex_limit)
            if cooked:
                shape.cooked_data = base64.b64encode(cooked).decode('ascii')
                shape.is_cooked = True
                shape.local_pos = (0, 0, 0)
                shape.local_rot = (1.0, 0.0, 0.0, 0.0)
                viz.invalidate_visualization_cache()
                self.report({'INFO'}, "Cooking Complete")
        except Exception as e:
            self.report({'ERROR'}, str(e))
        return {'FINISHED'}


class PHYSX_OT_fit_bounds_shape(bpy.types.Operator):
    bl_idname = "physx.fit_bounds_shape"
    bl_label = "Fit"
    shape_index: bpy.props.IntProperty(default=-1)

    def execute(self, context):
        obj = context.object
        px = obj.physx
        idx = self.shape_index if self.shape_index >= 0 else px.shape_index
        shape = px.shapes[idx]
        bbox = [Vector(b) for b in obj.bound_box]
        for v in bbox:
            v.x *= obj.scale.x;
            v.y *= obj.scale.y;
            v.z *= obj.scale.z
        min_v = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
        max_v = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
        size = max_v - min_v
        center = (min_v + max_v) / 2.0
        if shape.shape_type in ('CONVEX', 'TRIANGLE', 'HEIGHTFIELD'):
            shape.local_pos = (0, 0, 0)
        else:
            shape.local_pos = center
        if shape.shape_type == 'BOX':
            shape.dim_x = size.x / 2;
            shape.dim_y = size.y / 2;
            shape.dim_z = size.z / 2
        elif shape.shape_type == 'SPHERE':
            shape.dim_x = max(size) / 2.0
        elif shape.shape_type == 'CAPSULE':
            rad = max(size.x, size.y) / 2.0
            hh = (size.z / 2.0) - rad
            if hh < 0: hh = 0; rad = size.z / 2.0
            shape.dim_x = rad;
            shape.dim_y = hh
            shape.local_rot = Euler((0, math.radians(90), 0)).to_quaternion()
        elif shape.shape_type == 'HEIGHTFIELD':
            shape.dim_x = size.x / 2.0;
            shape.dim_y = size.y / 2.0;
            shape.dim_z = size.z / 2.0
        viz.invalidate_visualization_cache()
        context.area.tag_redraw()
        return {'FINISHED'}


class PHYSX_OT_calc_dynamics(bpy.types.Operator):
    bl_idname = "physx.calc_dynamics"
    bl_label = "Auto Calc"

    def execute(self, context):
        obj = context.object
        px = obj.physx
        try:
            from . import pxbridge as _bridge
            shapes_data = []
            densities = []
            for shape in px.shapes:
                raw = ""
                if shape.cooked_data:
                    raw = base64.b64decode(shape.cooked_data.encode('ascii'))
                dens = physx_utils.get_mat_density(shape.physics_material)
                densities.append(dens)
                l = shape.local_pos
                q = shape.local_rot
                data = {
                    "type": shape.shape_type, "data": raw, "dims": [shape.dim_x, shape.dim_y, shape.dim_z],
                    "pos": [l[0], l[1], l[2]], "rot": [q[1], q[2], q[3], q[0]], "mat": [0, 0, 0]
                    }
                shapes_data.append(data)
            res = _bridge.compute_mass_props(shapes_data, densities)
            if px.calc_mass: px.mass = res['mass']
            if px.calc_offset: px.com_offset = res['com']
            if px.calc_inertia: px.inertia = res['inertia']
        except Exception as e:
            print(f"Mass Calc Error: {e}")
        return {'FINISHED'}


class PHYSX_OT_shape_action(bpy.types.Operator):
    bl_idname = "physx.shape_action"
    bl_label = "Action"
    action: bpy.props.EnumProperty(items=[('ADD', "Add", ""), ('REMOVE', "Remove", "")])

    def execute(self, context):
        px = context.object.physx
        if self.action == 'ADD':
            s = px.shapes.add()
            s.name = f"Shape {len(px.shapes)}"
            bpy.ops.physx.fit_bounds_shape(shape_index=len(px.shapes) - 1)
            px.shape_index = len(px.shapes) - 1
        elif self.action == 'REMOVE' and len(px.shapes) > 0:
            px.shapes.remove(px.shape_index)
            px.shape_index = max(0, px.shape_index - 1)
        viz.invalidate_visualization_cache()
        return {'FINISHED'}


class PHYSX_OT_list_action(bpy.types.Operator):
    bl_idname = "physx.list_action"
    bl_label = "List Action"
    action: bpy.props.EnumProperty(items=[('ADD', "Add", ""), ('REMOVE', "Remove", "")])

    def execute(self, context):
        px_s = context.scene.physx
        if self.action == 'ADD':
            obj = context.active_object
            if not obj: return {'CANCELLED'}
            for item in px_s.actors:
                if item.obj_ref == obj: return {'CANCELLED'}
            item = px_s.actors.add()
            item.obj_ref = obj
            if len(obj.physx.shapes) == 0:
                s = obj.physx.shapes.add()
                s.name = "Shape 1"
                bpy.ops.physx.fit_bounds_shape(shape_index=0)
            px_s.actor_list_index = len(px_s.actors) - 1
        elif self.action == 'REMOVE':
            if len(px_s.actors) > 0: px_s.actors.remove(px_s.actor_list_index)
        viz.invalidate_visualization_cache()
        return {'FINISHED'}


class PHYSX_OT_reset_session(bpy.types.Operator):
    bl_idname = "physx.reset_session"
    bl_label = "Reset"

    def execute(self, context):
        try:
            from . import pxbridge as _bridge
            _bridge.reset()
            context.scene.physx.active_actor_count = 0
            context.scene.physx.scene_built = False
            for obj in _iter_cloth_objects(context):
                obj.cp77_cloth_handle = "-1"
                _set_cloth_state(obj, 'DRAFT', 'Reset')
        except Exception:
            pass
        return {'FINISHED'}