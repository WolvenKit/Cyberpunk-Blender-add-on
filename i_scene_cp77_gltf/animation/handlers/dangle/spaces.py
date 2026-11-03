from mathutils import Matrix, Vector

from ....animation.rig_binding import (
    is_read_rig_armature,
    resolve_bone_name,
    rig_space_contract,
)
from ....redSpace.contracts import (
    BLENDER_BONE_LOCAL_TO_RED_CURRENT,
    RED_LOCAL_TO_BLENDER_BONE_CURRENT,
    RIG_SPACE_CONTRACT_CURRENT,
    RIG_SPACE_CONTRACT_DIRECT,
)

from ....redSpace.transforms import (
    current_bone_local_transform_to_red,
    red_local_transform_to_current_bone,
)

RE_TO_BLENDER_BONE_LOCAL_CURRENT = Matrix(RED_LOCAL_TO_BLENDER_BONE_CURRENT)
BLENDER_BONE_LOCAL_TO_RE_CURRENT = Matrix(BLENDER_BONE_LOCAL_TO_RED_CURRENT)
_SUPPORTED_RIG_CONTRACTS = {RIG_SPACE_CONTRACT_CURRENT, RIG_SPACE_CONTRACT_DIRECT}


def re_to_blender_bone_local_matrix(arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return Matrix.Identity(4)
    return RE_TO_BLENDER_BONE_LOCAL_CURRENT


def blender_bone_local_to_re_matrix(arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return Matrix.Identity(4)
    return BLENDER_BONE_LOCAL_TO_RE_CURRENT


def re_axis_to_blender_bone(axis, arm_obj=None):
    return re_to_blender_bone_local_matrix(arm_obj).to_3x3() @ Vector(axis)


def blender_bone_axis_to_re(axis, arm_obj=None):
    return blender_bone_local_to_re_matrix(arm_obj).to_3x3() @ Vector(axis)


def re_local_transform_to_blender_bone(matrix, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(red_local_transform_to_current_bone(matrix))


def blender_bone_local_transform_to_re(matrix, arm_obj=None):
    if rig_space_contract(arm_obj) == RIG_SPACE_CONTRACT_DIRECT:
        return matrix.copy()
    return Matrix(current_bone_local_transform_to_red(matrix))


def operation_uses_default_branch(operation) -> bool:
    """Return whether an imported graph operation is active without runtime tags.

    REDengine ``animAnimNode_StaticSwitch`` branches are condition-driven. The
    editor has no runtime visual-tag context, so its neutral evaluation uses the
    False branch. Older imported editor states may still contain operations from
    both branches; a ``.True`` path segment identifies the inactive branch.
    """
    graph_path = str(getattr(operation, "graph_path", "") or "")
    return "True" not in graph_path.split(".")


def executable_node_indices(state):
    """Return Dangle and Drag indices that participate in graph evaluation.

    WolvenKit exports may retain disconnected authoring nodes. They remain
    editable, but are not runtime requirements unless the graph has no
    evaluation order, in which case the editor's legacy all-nodes fallback
    applies.
    """
    raw_operations = getattr(state, "evaluation_order", ())
    operations = tuple(raw_operations) if raw_operations is not None else ()
    if not operations:
        return (
            set(range(len(getattr(state, "dangle_nodes", ())))),
            set(range(len(getattr(state, "drag_nodes", ())))),
        )

    dangle_indices = set()
    drag_indices = set()
    for operation in operations:
        if not operation_uses_default_branch(operation):
            continue
        node_index = int(getattr(operation, "node_index", -1))
        if node_index < 0:
            continue
        node_type = str(getattr(operation, "node_type", "") or "")
        if node_type == "DANGLE":
            dangle_indices.add(node_index)
        elif node_type == "DRAG":
            drag_indices.add(node_index)
    return dangle_indices, drag_indices


def iter_state_bone_references(state, executable_only=False):
    """Yield ``(role, authored_name)`` for required rig references.

    When ``executable_only`` is true, disconnected authoring-only graph nodes
    are excluded from MetaRig validation.
    """
    seen = set()

    def emit(role, name):
        value = str(name or "")
        key = (role, value)
        if value and key not in seen:
            seen.add(key)
            return key
        return None

    active_dangles, active_drags = executable_node_indices(state)

    for node_index, dnode in enumerate(getattr(state, "dangle_nodes", ())):
        if executable_only and node_index not in active_dangles:
            continue
        for shape in getattr(dnode, "collision_shapes", ()):
            item = emit(f"dangle[{node_index}] collision shape", shape.bone_name)
            if item:
                yield item
        for chain_index, chain in enumerate(getattr(dnode, "chains", ())):
            for particle_index, particle in enumerate(getattr(chain, "particles", ())):
                prefix = f"dangle[{node_index}] chain[{chain_index}] particle[{particle_index}]"
                item = emit(prefix, particle.bone_name)
                if item:
                    yield item
                if getattr(particle, "direction_reference_bone", ""):
                    item = emit(f"{prefix} direction reference", particle.direction_reference_bone)
                    if item:
                        yield item
                for constraint in getattr(particle, "link_constraints", ()):
                    item = emit(f"{prefix} link target", constraint.target_bone)
                    if item:
                        yield item
                for constraint in getattr(particle, "ellipsoid_constraints", ()):
                    item = emit(f"{prefix} ellipsoid target", constraint.target_bone)
                    if item:
                        yield item
                for constraint in getattr(particle, "pendulum_constraints", ()):
                    item = emit(f"{prefix} cone attachment", constraint.target_bone)
                    if item:
                        yield item

    if not executable_only or active_dangles:
        for shape in getattr(state, "collision_shapes", ()):
            item = emit("global collision shape", shape.bone_name)
            if item:
                yield item

    for drag_index, drag in enumerate(getattr(state, "drag_nodes", ())):
        if executable_only and drag_index not in active_drags:
            continue
        source = drag.source_bone_name or drag.bone_name
        item = emit(f"drag[{drag_index}] source", source)
        if item:
            yield item
        item = emit(f"drag[{drag_index}] target", drag.bone_name)
        if item:
            yield item


def unresolved_state_bones(arm_obj, state, executable_only=False):
    return [
        (role, name)
        for role, name in iter_state_bone_references(
            state, executable_only=executable_only
        )
        if resolve_bone_name(arm_obj, name) == ""
    ]


def armature_space_errors(arm_obj, tolerance=1e-5):
    if arm_obj is None or getattr(arm_obj, "type", None) != "ARMATURE":
        return ["The Dangle target must be an armature"]
    data = getattr(arm_obj, "data", None)
    stored_contract = data.get("cp77_rig_space_contract") if data is not None else None
    if stored_contract is not None and stored_contract not in _SUPPORTED_RIG_CONTRACTS:
        return [f"Unsupported CP77 rig-space contract: {stored_contract}"]
    if stored_contract is None and not is_read_rig_armature(arm_obj):
        return [
            "The Dangle target must be a read_rig armature/MetaRig or expose "
            "an explicit CP77 rig-space contract"
        ]
    matrix = arm_obj.matrix_world
    determinant = matrix.determinant()
    if abs(determinant) <= 1e-12:
        return ["The armature world transform is singular"]
    if determinant < 0.0:
        return [
            "The armature world transform is mirrored; apply transforms before "
            "running Dangle physics"
        ]
    scale = matrix.to_scale()
    if min(abs(value) for value in scale) <= 1e-8:
        return ["The armature has a zero world-scale axis"]
    if any(abs(abs(value) - 1.0) > tolerance for value in scale):
        return [
            "The armature object scale must be applied before running Dangle "
            "physics; REDengine converts world forces by orientation only"
        ]
    return []


def world_vector_to_model(arm_obj, vector):
    """Match REDengine WorldTransform::GetInverse().GetOrientation()."""
    return arm_obj.matrix_world.to_quaternion().inverted() @ Vector(vector)


def model_vector_to_world(arm_obj, vector):
    return arm_obj.matrix_world.to_quaternion() @ Vector(vector)


def world_direction_to_model(arm_obj, direction):
    return world_vector_to_model(arm_obj, direction)


def model_position_to_world(arm_obj, position):
    return arm_obj.matrix_world @ Vector(position)


def world_position_to_model(arm_obj, position):
    return arm_obj.matrix_world.inverted_safe() @ Vector(position)


def previous_model_to_current_model(previous_matrix_world, current_matrix_world):
    # p_world = previous_world @ p_previous_model
    # p_current_model = inverse(current_world) @ p_world
    return current_matrix_world.inverted_safe() @ previous_matrix_world
