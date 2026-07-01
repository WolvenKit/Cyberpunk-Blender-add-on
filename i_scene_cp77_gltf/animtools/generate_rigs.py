from __future__ import annotations
from collections import defaultdict
from typing import Optional, Tuple, Dict, List, Iterable

import bpy
from mathutils import Color, Matrix, Vector

from ..main.bartmoss_functions import (
    store_current_context,
    restore_previous_context,
    safe_mode_switch,
    select_objects,
)


# CP77 source bone  →  metarig bone (Rigify human metarig naming)
CP77_TO_METARIG: Dict[str, str] = {
    'Root':          'root',
    'Hips':          'pelvis',
    'Spine':         'spine',
    'Spine1':        'spine.001',
    'Spine2':        'spine.002',
    'Spine3':        'spine.003',
    'Neck':          'spine.004',
    'Neck1':         'spine.005',
    'Head':          'spine.006',
    'LeftEye':       'eye.L',
    'RightEye':      'eye.R',

    'LeftUpLeg':     'thigh.L',
    'LeftLeg':       'shin.L',
    'LeftFoot':      'foot.L',
    'LeftHeel':      'heel.L',
    'LeftToeBase':   'toe.L',
    'RightUpLeg':    'thigh.R',
    'RightLeg':      'shin.R',
    'RightFoot':     'foot.R',
    'RightHeel':     'heel.R',
    'RightToeBase':  'toe.R',

    'LeftShoulder':  'shoulder.L',
    'LeftArm':       'upper_arm.L',
    'LeftForeArm':   'forearm.L',
    'LeftHand':      'hand.L',
    'WeaponLeft':    'weapon.L',
    'RightShoulder': 'shoulder.R',
    'RightArm':      'upper_arm.R',
    'RightForeArm':  'forearm.R',
    'RightHand':     'hand.R',
    'WeaponRight':   'weapon.R',

    'LeftInHandThumb':   'palm.01.L',
    'LeftHandThumb1':    'thumb.01.L',
    'LeftHandThumb2':    'thumb.02.L',
    'LeftInHandIndex':   'palm.02.L',
    'LeftHandIndex1':    'f_index.01.L',
    'LeftHandIndex2':    'f_index.02.L',
    'LeftHandIndex3':    'f_index.03.L',
    'LeftInHandMiddle':  'palm.03.L',
    'LeftHandMiddle1':   'f_middle.01.L',
    'LeftHandMiddle2':   'f_middle.02.L',
    'LeftHandMiddle3':   'f_middle.03.L',
    'LeftInHandRing':    'palm.04.L',
    'LeftHandRing1':     'f_ring.01.L',
    'LeftHandRing2':     'f_ring.02.L',
    'LeftHandRing3':     'f_ring.03.L',
    'LeftInHandPinky':   'palm.05.L',
    'LeftHandPinky1':    'f_pinky.01.L',
    'LeftHandPinky2':    'f_pinky.02.L',
    'LeftHandPinky3':    'f_pinky.03.L',

    'RightInHandThumb':  'palm.01.R',
    'RightHandThumb1':   'thumb.01.R',
    'RightHandThumb2':   'thumb.02.R',
    'RightInHandIndex':  'palm.02.R',
    'RightHandIndex1':   'f_index.01.R',
    'RightHandIndex2':   'f_index.02.R',
    'RightHandIndex3':   'f_index.03.R',
    'RightInHandMiddle': 'palm.03.R',
    'RightHandMiddle1':  'f_middle.01.R',
    'RightHandMiddle2':  'f_middle.02.R',
    'RightHandMiddle3':  'f_middle.03.R',
    'RightInHandRing':   'palm.04.R',
    'RightHandRing1':    'f_ring.01.R',
    'RightHandRing2':    'f_ring.02.R',
    'RightHandRing3':    'f_ring.03.R',
    'RightInHandPinky':  'palm.05.R',
    'RightHandPinky1':   'f_pinky.01.R',
    'RightHandPinky2':   'f_pinky.02.R',
    'RightHandPinky3':   'f_pinky.03.R',
}

METARIG_TO_CP77: Dict[str, str] = {v: k for k, v in CP77_TO_METARIG.items()}


# Metarig bone  →  rigify_type assignment
RIGIFY_TYPES: Dict[str, str] = {
    'pelvis':     'spines.basic_spine',
    'spine.004':  'spines.super_head',
    'eye.L':      'basic.super_copy',
    'eye.R':      'basic.super_copy',
    'thigh.L':    'limbs.leg',
    'thigh.R':    'limbs.leg',
    'upper_arm.L': 'limbs.arm',
    'upper_arm.R': 'limbs.arm',
    'weapon.L':   'basic.super_copy',
    'weapon.R':   'basic.super_copy',
}
for _side in ('L', 'R'):
    for _finger in ('thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01'):
        RIGIFY_TYPES[f'{_finger}.{_side}'] = 'limbs.super_finger'


# Parent / connect chains for the metarig prep pass
CHAINS: List[List[str]] = [
    ['pelvis', 'spine', 'spine.001', 'spine.002', 'spine.003'],
    ['spine.004', 'spine.005', 'spine.006'],
]
for _s in ('L', 'R'):
    CHAINS.append([f'thigh.{_s}', f'shin.{_s}', f'foot.{_s}'])
    CHAINS.append([f'upper_arm.{_s}', f'forearm.{_s}', f'hand.{_s}'])


# Per-side metarig finger chains (proximal → distal), excluding the palm bone.
# Drives terminal-tip repair and roll alignment in the metarig prep pass.
METARIG_FINGER_CHAINS: Dict[str, Tuple[Tuple[str, ...], ...]] = {}
for _s in ('L', 'R'):
    METARIG_FINGER_CHAINS[_s] = (
        (f'thumb.01.{_s}', f'thumb.02.{_s}'),
        tuple(f'f_index.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_middle.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_ring.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_pinky.0{_j}.{_s}' for _j in range(1, 4)),
    )


# Bone collection layout: name → (members, row, color_set_id)
COLLECTIONS: Dict[str, Tuple[List[str], int, int]] = {
    'Root':   (['root', 'pelvis'], 0, 1),
    'Torso':  (['spine', 'spine.001', 'spine.002', 'spine.003'], 3, 5),
    'Face':   (['spine.004', 'spine.005', 'spine.006', 'eye.L', 'eye.R'], 2, 3),
}
for _s in ('L', 'R'):
    COLLECTIONS[f'Arms.{_s}'] = (
        [f'shoulder.{_s}', f'upper_arm.{_s}', f'forearm.{_s}', f'hand.{_s}'], 3, 5,
    )
    COLLECTIONS[f'Legs.{_s}'] = (
        [f'thigh.{_s}', f'shin.{_s}', f'foot.{_s}', f'heel.{_s}', f'toe.{_s}'], 4, 5,
    )
    COLLECTIONS[f'Fingers.{_s}'] = (
        [f'palm.0{_i}.{_s}' for _i in range(1, 6)]
        + [f'thumb.0{_i}.{_s}' for _i in range(1, 3)]
        + [f'{_f}.0{_j}.{_s}'
           for _f in ('f_index', 'f_middle', 'f_ring', 'f_pinky')
           for _j in range(1, 4)],
        4, 4,
    )
    COLLECTIONS[f'Weapons.{_s}'] = ([f'weapon.{_s}'], 5, 6)


# Rigify color sets, in the canonical order Rigify expects
COLOR_SETS: List[Tuple[str, Tuple[float, float, float], Tuple[float, float, float]]] = [
    ('Root',    (0.549, 1.000, 1.000), (0.435, 0.184, 0.416)),
    ('IK',      (0.549, 1.000, 1.000), (0.604, 0.000, 0.000)),
    ('Special', (0.549, 1.000, 1.000), (0.957, 0.788, 0.047)),
    ('Tweak',   (0.549, 1.000, 1.000), (0.039, 0.212, 0.580)),
    ('FK',      (0.549, 1.000, 1.000), (0.118, 0.569, 0.035)),
    ('Extra',   (0.549, 1.000, 1.000), (0.969, 0.251, 0.094)),
]

SELECT_COLOR: Tuple[float, float, float] = (0.314, 0.784, 1.000)


# Constraint naming. Both directions use identifiable names so we can locate/mute/unmute them deterministically
FORWARD_CONSTRAINT: str = 'CP77_RigifyDrivesSource'
REVERSE_CONSTRAINT: str = 'CP77_SourceDrivesRigify'

DIRECTION_FORWARD: str = 'forward'
DIRECTION_REVERSE: str = 'reverse'

FORWARD_LOCATION_BONES = {'Root', 'Hips'}
FORWARD_LIMITED_LOCATION_BONES = {'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot'}
LIMITED_LOCATION_OFFSETS = {
    'LeftHand': 0.35,
    'RightHand': 0.35,
    'LeftFoot': 1.25,
    'RightFoot': 1.25,
}
MAX_LIMITED_LOCATION_OFFSET = 0.35

# CP77 shoulder/clavicle joints are not equivalent to generated Rigify shoulder
# controls. The controls affect the generated arm chain before source sync, so
# skipping only the CP77 shoulder bones is insufficient. Disable these controls
# at the Rigify side and keep the source shoulder joints at rest.
PALM_METARIG_BONES = {
    f'palm.0{i}.{side}'
    for side in ('L', 'R')
    for i in range(1, 6)
}

PALM_CP77_BONES = {
    cp77
    for cp77, meta in CP77_TO_METARIG.items()
    if meta in PALM_METARIG_BONES
}

NEUTRALIZED_RIGIFY_CONTROLS = {'shoulder.L', 'shoulder.R'} | PALM_METARIG_BONES
FORWARD_REST_ONLY_BONES = {'LeftShoulder', 'RightShoulder'} | PALM_CP77_BONES


# Stale forward constraint names removed before matrix-basis sync is enabled.
FORWARD_CONSTRAINT_NAMES = (
    FORWARD_CONSTRAINT,
    f'{FORWARD_CONSTRAINT}Location',
    'CP77_SourcePoseSyncBridge',
)

_CP77_BASIS_SYNC_ACTIVE = False

# Stored on the source armature as evaluated generated-rig neutral matrices.
# The source sync uses these instead of raw generated bone rest matrices so a
# freshly generated neutral Rigify pose produces an identity source delta.
FORWARD_NEUTRAL_PROP_PREFIX = 'cp77_forward_neutral_'


CP77_TO_RIGIFY_REVERSE: Dict[str, str] = {
    'Hips':           'torso',
    'Spine':          'spine_fk',
    'Spine1':         'spine_fk.001',
    'Spine2':         'spine_fk.002',
    'Spine3':         'spine_fk.003',
    'Head':           'head',
    'LeftEye':        'eye.L',
    'RightEye':       'eye.R',

    'LeftShoulder':   'shoulder.L',
    'LeftArm':        'upper_arm_fk.L',
    'LeftForeArm':    'forearm_fk.L',
    'LeftHand':       'hand_fk.L',
    'RightShoulder':  'shoulder.R',
    'RightArm':       'upper_arm_fk.R',
    'RightForeArm':   'forearm_fk.R',
    'RightHand':      'hand_fk.R',

    'LeftUpLeg':      'thigh_fk.L',
    'LeftLeg':        'shin_fk.L',
    'LeftFoot':       'foot_fk.L',
    'LeftToeBase':    'toe_fk.L',
    'RightUpLeg':     'thigh_fk.R',
    'RightLeg':       'shin_fk.R',
    'RightFoot':      'foot_fk.R',
    'RightToeBase':   'toe_fk.R',
}


def _resolve_target(rig_bone_names: set, base: str) -> Optional[str]:
    """Locate the bone on the rigify rig that best represents *base*.

    Order: DEF- → ORG- → MCH- → bare name. Used as a general fallback and by
    reverse-direction lookups when no explicit FK control is specified in
    CP77_TO_RIGIFY_REVERSE.
    """
    for cand in (f'DEF-{base}', f'ORG-{base}', f'MCH-{base}', base):
        if cand in rig_bone_names:
            return cand
    return None


def _first_existing(names: set, candidates: Iterable[str]) -> Optional[str]:
    for name in candidates:
        if name in names:
            return name
    return None


def _is_finger_or_palm_metarig_bone(name: str) -> bool:
    return (
        name.startswith('palm.')
        or name.startswith('thumb.')
        or name.startswith('f_index.')
        or name.startswith('f_middle.')
        or name.startswith('f_ring.')
        or name.startswith('f_pinky.')
    )


def _resolve_forward_target(cp77_bone: str, metarig_bone: str,
                            rig_bone_names: set) -> Optional[str]:
    """Resolve the generated Rigify bone sampled by forward source sync.

    Forward sync should sample the generated deformation result where possible.
    ORG bones are only a final fallback, and MCH bones are intentionally never
    used for the mesh-bound source rig.
    """
    special = {
        'Root': ('root', 'DEF-root', 'ORG-root'),
        'Hips': ('DEF-pelvis', 'pelvis', 'torso', 'ORG-pelvis'),
        'LeftShoulder': ('DEF-shoulder.L', 'shoulder.L', 'ORG-shoulder.L'),
        'RightShoulder': ('DEF-shoulder.R', 'shoulder.R', 'ORG-shoulder.R'),
        'WeaponLeft': ('weapon.L', 'DEF-weapon.L', 'ORG-weapon.L'),
        'WeaponRight': ('weapon.R', 'DEF-weapon.R', 'ORG-weapon.R'),
    }
    target = _first_existing(rig_bone_names, special.get(cp77_bone, ()))
    if target is not None:
        return target

    if _is_finger_or_palm_metarig_bone(metarig_bone):
        return _first_existing(rig_bone_names, (
            f'DEF-{metarig_bone}',
            f'ORG-{metarig_bone}',
            metarig_bone,
        ))

    return _first_existing(rig_bone_names, (
        f'DEF-{metarig_bone}',
        metarig_bone,
        f'ORG-{metarig_bone}',
    ))


def _bone_depth(armature: bpy.types.Object, bone_name: str) -> int:
    bone = armature.data.bones.get(bone_name) if armature and armature.type == 'ARMATURE' else None
    depth = 0
    seen = set()
    while bone is not None and bone.parent is not None and bone.name not in seen:
        seen.add(bone.name)
        depth += 1
        bone = bone.parent
    return depth


def _safe_matrix_inverse(m):
    return m.inverted_safe() if hasattr(m, 'inverted_safe') else m.inverted()


def _copy_matrix3(dst, src) -> None:
    for r in range(3):
        for c in range(3):
            dst[r][c] = src[r][c]


def set_rigify_coll_prop(coll, name: str, value) -> None:
    """
    Write a Rigify bone-collection property across Blender versions
    """
    try:
        setattr(coll, name, value)
    except (AttributeError, TypeError):
        coll[name] = value


def get_rigify_coll_prop(coll, name: str, default=0):
    """Read a Rigify bone-collection property across Blender versions."""
    if hasattr(coll, name):
        return getattr(coll, name)
    return coll.get(name, default)


def _reverse_target_for(cp77_bone: str, metarig_bone: Optional[str],
                        rig_bone_names: set) -> Optional[str]:
    """Pick the rigify target bone used when source drives rigify."""
    explicit = CP77_TO_RIGIFY_REVERSE.get(cp77_bone)
    if explicit and explicit in rig_bone_names:
        return explicit
    if metarig_bone is not None:
        return _resolve_target(rig_bone_names, metarig_bone)
    return None


# Public pair-lookup helpers used by the UI 

def find_pair(obj: Optional[bpy.types.Object]
              ) -> Tuple[Optional[bpy.types.Object], Optional[bpy.types.Object]]:
    """Resolve (source, rigify_rig) given any armature in the trio.

    Accepts the source rig, the metarig, or the generated rigify rig; returns
    the source and rigify pair if both are still present in the .blend.
    """
    if obj is None or obj.type != 'ARMATURE':
        return None, None
    arm = obj.data

    source_name = arm.get('cp77_source_rig')
    if source_name:
        source = bpy.data.objects.get(source_name)
        if source is not None and source.type == 'ARMATURE':
            rig_name = source.data.get('cp77_rigify_rig')
            rig = bpy.data.objects.get(rig_name) if rig_name else None
            return source, (rig if rig and rig.type == 'ARMATURE' else None)

    rig_name = arm.get('cp77_rigify_rig')
    if rig_name:
        rig = bpy.data.objects.get(rig_name)
        if rig is not None and rig.type == 'ARMATURE':
            return obj, rig

    return None, None


def get_metarig(source: bpy.types.Object) -> Optional[bpy.types.Object]:
    name = source.data.get('cp77_metarig') if source and source.data else None
    if not name:
        return None
    obj = bpy.data.objects.get(name)
    return obj if obj and obj.type == 'ARMATURE' else None


def get_constraint_direction(source: bpy.types.Object) -> str:
    if not source or not source.data:
        return DIRECTION_FORWARD
    return source.data.get('cp77_constraint_direction', DIRECTION_FORWARD)


def _make_copy_transforms(bone: bpy.types.PoseBone, name: str,
                          target: bpy.types.Object, subtarget: str
                          ) -> bpy.types.Constraint:
    """Create or refresh a named COPY_TRANSFORMS constraint at the end of the stack."""
    existing = bone.constraints.get(name)
    if existing is not None:
        bone.constraints.remove(existing)
    c = bone.constraints.new('COPY_TRANSFORMS')
    c.name = name
    c.target = target
    c.subtarget = subtarget
    c.target_space = 'WORLD'
    c.owner_space = 'WORLD'
    if hasattr(c, 'use_offset'):
        c.use_offset = False
    if hasattr(c, 'mix_mode'):
        c.mix_mode = 'REPLACE'
    return c


def _set_constraint_mute(armature_obj: bpy.types.Object,
                         constraint_name: str, mute: bool) -> int:
    """Mute or unmute every same-named constraint on the rig. Returns count."""
    n = 0
    for pb in armature_obj.pose.bones:
        c = pb.constraints.get(constraint_name)
        if c is not None:
            c.mute = mute
            n += 1
    return n


def _neutralize_rigify_controls(rig: bpy.types.Object) -> int:
    """Keep known non-export-safe Rigify controls from driving source sync.

    Shoulder and palm controls are Rigify control/offset constructs, not
    equivalent CP77 deform joints. If they remain movable, their transforms
    enter the evaluated chain before source sync samples it.
    """
    if rig is None or rig.type != 'ARMATURE':
        return 0
    n = 0
    for name in NEUTRALIZED_RIGIFY_CONTROLS:
        pb = rig.pose.bones.get(name)
        if pb is None:
            continue
        pb.matrix_basis.identity()
        pb.lock_location = (True, True, True)
        pb.lock_rotation = (True, True, True)
        pb.lock_rotation_w = True
        pb.lock_scale = (True, True, True)
        pb.hide = True
        n += 1
    return n


def _clear_forward_constraints(source: bpy.types.Object) -> int:
    """Remove named forward-driving constraints from the source rig."""
    removed = 0
    if source is None or source.type != 'ARMATURE':
        return removed
    for pb in source.pose.bones:
        for name in FORWARD_CONSTRAINT_NAMES:
            c = pb.constraints.get(name)
            if c is not None:
                pb.constraints.remove(c)
                removed += 1
    return removed


def _rotation_only_3x3(matrix: Matrix) -> Matrix:
    """Return an orthonormal rotation matrix, discarding scale and shear."""
    return matrix.to_quaternion().to_matrix()


def _matrix_to_flat(matrix: Matrix) -> List[float]:
    return [float(matrix[r][c]) for r in range(4) for c in range(4)]


def _flat_to_matrix(values) -> Optional[Matrix]:
    try:
        flat = [float(v) for v in values]
    except Exception:
        return None
    if len(flat) != 16:
        return None
    return Matrix((
        flat[0:4],
        flat[4:8],
        flat[8:12],
        flat[12:16],
    ))


def _forward_neutral_prop(cp77_bone: str) -> str:
    return FORWARD_NEUTRAL_PROP_PREFIX + cp77_bone


def _get_forward_neutral_pose(source: bpy.types.Object,
                              cp77_bone: str) -> Optional[Matrix]:
    if source is None or source.type != 'ARMATURE':
        return None
    return _flat_to_matrix(source.data.get(_forward_neutral_prop(cp77_bone), ()))


def _has_forward_neutral_pose(source: bpy.types.Object,
                              rig: bpy.types.Object) -> bool:
    if source is None or rig is None:
        return False
    rig_bone_names = set(rig.pose.bones.keys())
    for cp77_bone, metarig_bone in CP77_TO_METARIG.items():
        if cp77_bone in FORWARD_REST_ONLY_BONES:
            continue
        if source.pose.bones.get(cp77_bone) is None:
            continue
        target_name = _resolve_forward_target(cp77_bone, metarig_bone, rig_bone_names)
        if target_name is None:
            continue
        if _get_forward_neutral_pose(source, cp77_bone) is None:
            return False
    return True


def _capture_forward_neutral_pose(source: bpy.types.Object,
                                  rig: bpy.types.Object,
                                  depsgraph=None) -> int:
    """Capture generated Rigify neutral pose matrices for source sync.

    Rigify DEF bones often do not evaluate exactly to their edit-bone rest
    matrix at generation time because MCH constraints and control layers are
    already active. Using bone.matrix_local as the neutral reference therefore
    injects a pose delta into the CP77 source at frame zero. Capturing the
    evaluated generated pose makes neutral Rigify → neutral source an identity
    operation.
    """
    if source is None or rig is None:
        return 0
    if source.type != 'ARMATURE' or rig.type != 'ARMATURE':
        return 0

    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None

    try:
        rig_eval = rig.evaluated_get(depsgraph) if depsgraph is not None else rig
    except Exception:
        rig_eval = rig

    rig_pose = rig_eval.pose.bones
    rig_bone_names = set(rig_pose.keys())
    captured = 0

    for cp77_bone, metarig_bone in CP77_TO_METARIG.items():
        if cp77_bone in FORWARD_REST_ONLY_BONES:
            continue
        if source.pose.bones.get(cp77_bone) is None:
            continue

        target_name = _resolve_forward_target(cp77_bone, metarig_bone, rig_bone_names)
        if target_name is None:
            continue

        target_pb = rig_pose.get(target_name)
        if target_pb is None:
            continue

        source.data[_forward_neutral_prop(cp77_bone)] = _matrix_to_flat(target_pb.matrix.copy())
        captured += 1

    return captured


def _basis_from_world_rest_delta(source: bpy.types.Object,
                                 rig: bpy.types.Object,
                                 src_pb: bpy.types.PoseBone,
                                 target_pb: bpy.types.PoseBone,
                                 target_rest: Matrix,
                                 copy_location: bool,
                                 limited_location: bool = False,
                                 target_neutral: Optional[Matrix] = None) -> Matrix:
    """Solve source matrix_basis from the target's evaluated neutral delta.

    The neutral reference is the generated Rigify bone's evaluated matrix
    captured immediately after generation. This is deliberately different from
    target_rest: Rigify DEF bones can evaluate with constraint/MCH offsets even
    when the visible controls are at zero. Using the captured neutral prevents
    the source fingers from receiving an offset as soon as the rig is generated.
    """
    source_rest = src_pb.bone.matrix_local.copy()

    target_pose_world = rig.matrix_world @ target_pb.matrix.copy()
    target_neutral_local = target_neutral if target_neutral is not None else target_rest
    target_neutral_world = rig.matrix_world @ target_neutral_local.copy()
    source_rest_world = source.matrix_world @ source_rest

    target_delta_world = target_pose_world @ _safe_matrix_inverse(target_neutral_world)
    desired_pose_world = target_delta_world @ source_rest_world
    desired_pose_local = _safe_matrix_inverse(source.matrix_world) @ desired_pose_world

    if src_pb.parent is not None:
        parent_pose = src_pb.parent.matrix.copy()
        parent_rest = src_pb.parent.bone.matrix_local.copy()
        bind = parent_pose @ _safe_matrix_inverse(parent_rest) @ source_rest
    else:
        bind = source_rest

    basis = _safe_matrix_inverse(bind) @ desired_pose_local

    result = Matrix.Identity(4)
    _copy_matrix3(result, _rotation_only_3x3(basis))

    if copy_location or limited_location:
        loc = basis.translation.copy()
        if limited_location:
            limit = LIMITED_LOCATION_OFFSETS.get(src_pb.name, MAX_LIMITED_LOCATION_OFFSET)
            if loc.length > limit:
                loc = loc.normalized() * limit
        result.translation = loc

    return result

def _refresh_pose_matrices(obj: bpy.types.Object) -> None:
    """Force Blender to refresh dependent pose matrices after parent basis writes."""
    try:
        obj.update_tag(refresh={'OBJECT', 'DATA'})
        bpy.context.view_layer.update()
    except Exception:
        pass

def sync_source_from_rigify(source: bpy.types.Object,
                            rig: bpy.types.Object,
                            depsgraph=None) -> int:
    """Apply Rigify evaluated world-rest deltas to the CP77 source matrix_basis.

    Source bones are processed by hierarchy depth and the pose is refreshed once
    per depth level. This preserves the parent-refresh behaviour needed by feet
    and hands without forcing a full view-layer update after every single bone.
    Finger phalanges use the evaluated Rigify DEF-chain local pose delta,
    converted into the CP77 source joint basis without copying translation.
    """
    if source is None or rig is None:
        return 0
    if source.type != 'ARMATURE' or rig.type != 'ARMATURE':
        return 0

    if depsgraph is None:
        try:
            depsgraph = bpy.context.evaluated_depsgraph_get()
        except Exception:
            depsgraph = None

    try:
        rig_eval = rig.evaluated_get(depsgraph) if depsgraph is not None else rig
    except Exception:
        rig_eval = rig

    rig_pose = rig_eval.pose.bones
    rig_bone_names = set(rig_pose.keys())
    rig_data_bones = rig.data.bones

    entries = []
    for cp77_bone, metarig_bone in CP77_TO_METARIG.items():
        src_pb = source.pose.bones.get(cp77_bone)
        if src_pb is None:
            continue

        if cp77_bone in FORWARD_REST_ONLY_BONES:
            entries.append((_bone_depth(source, cp77_bone), cp77_bone, metarig_bone, src_pb, None, None))
            continue

        target_name = _resolve_forward_target(cp77_bone, metarig_bone, rig_bone_names)
        if target_name is None:
            continue

        target_pb = rig_pose.get(target_name)
        if target_pb is None:
            continue

        target_rest_bone = rig_data_bones.get(target_name)
        target_rest = (target_rest_bone.matrix_local.copy()
                       if target_rest_bone is not None
                       else target_pb.bone.matrix_local.copy())
        entries.append((_bone_depth(source, cp77_bone), cp77_bone, metarig_bone, src_pb, target_pb, target_rest))

    synced = 0
    current_depth = None
    for depth, cp77_bone, metarig_bone, src_pb, target_pb, target_rest in sorted(entries, key=lambda item: item[0]):
        if current_depth is not None and depth != current_depth:
            _refresh_pose_matrices(source)
        current_depth = depth

        if cp77_bone in FORWARD_REST_ONLY_BONES:
            src_pb.matrix_basis.identity()
            synced += 1
            continue

        neutral = _get_forward_neutral_pose(source, cp77_bone)
        basis = _basis_from_world_rest_delta(
            source,
            rig_eval,
            src_pb,
            target_pb,
            target_rest,
            cp77_bone in FORWARD_LOCATION_BONES,
            cp77_bone in FORWARD_LIMITED_LOCATION_BONES,
            neutral,
        )

        src_pb.matrix_basis = basis
        synced += 1

    if current_depth is not None:
        _refresh_pose_matrices(source)
    return synced

def _cp77_basis_sync_handler(*args) -> None:
    global _CP77_BASIS_SYNC_ACTIVE
    if _CP77_BASIS_SYNC_ACTIVE:
        return
    depsgraph = next((a for a in reversed(args) if hasattr(a, 'id_eval_get')), None)
    _CP77_BASIS_SYNC_ACTIVE = True
    try:
        for source in tuple(bpy.data.objects):
            if source.type != 'ARMATURE':
                continue
            if not source.data.get('cp77_forward_sync_enabled', False):
                continue
            rig_name = source.data.get('cp77_rigify_rig')
            rig = bpy.data.objects.get(rig_name) if rig_name else None
            if rig is None or rig.type != 'ARMATURE':
                continue
            _neutralize_rigify_controls(rig)
            sync_source_from_rigify(source, rig, depsgraph=depsgraph)
    finally:
        _CP77_BASIS_SYNC_ACTIVE = False

def ensure_basis_sync_handler() -> None:
    """
    Install the current sync handler and replace previous sync handlers.
    Blender keeps app handlers alive after script reloads, so replace handlers
    by function name instead of only checking whether one exists
    """
    handlers = bpy.app.handlers.depsgraph_update_post
    handler_names = {'_cp77_basis_sync_handler', '_cp77_sync_handler'}
    for h in tuple(handlers):
        if getattr(h, '__name__', '') in handler_names:
            handlers.remove(h)
    handlers.append(_cp77_basis_sync_handler)


def _build_forward_constraints(source: bpy.types.Object,
                               rig: bpy.types.Object,
                               recapture_neutral: bool = False) -> int:
    """Enable matrix-basis forward sync from Rigify to CP77 source bones."""
    _clear_forward_constraints(source)
    _neutralize_rigify_controls(rig)
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
    except Exception:
        depsgraph = None

    if recapture_neutral or not _has_forward_neutral_pose(source, rig):
        _capture_forward_neutral_pose(source, rig, depsgraph=depsgraph)

    source.data['cp77_forward_sync_enabled'] = True
    ensure_basis_sync_handler()
    select_objects(source)
    safe_mode_switch('POSE')
    return sync_source_from_rigify(source, rig, depsgraph=depsgraph)


def _build_reverse_constraints(source: bpy.types.Object,
                               rig: bpy.types.Object) -> int:
    """Place COPY_TRANSFORMS on rigify control bones, targeting the source rig.

    Lazy-created on first reverse-direction toggle, then persist muted.
    """
    rig_bone_names = set(rig.data.bones.keys())
    select_objects(rig)
    safe_mode_switch('POSE')
    n = 0
    for source_bone in source.pose.bones:
        meta = CP77_TO_METARIG.get(source_bone.name)
        target_name = _reverse_target_for(source_bone.name, meta, rig_bone_names)
        if not target_name:
            continue
        target_pb = rig.pose.bones.get(target_name)
        if target_pb is None:
            continue
        _make_copy_transforms(target_pb, REVERSE_CONSTRAINT, source, source_bone.name)
        n += 1
    return n


def set_constraint_direction(source: bpy.types.Object,
                             rig: bpy.types.Object,
                             direction: str) -> Tuple[bool, str]:
    """Toggle which side drives which. Creates the reverse-side constraints lazily."""
    if direction not in (DIRECTION_FORWARD, DIRECTION_REVERSE):
        return False, f"Unknown direction '{direction}'"
    if source is None or rig is None:
        return False, 'Missing source or rigify rig'

    store_current_context()
    try:
        if direction == DIRECTION_FORWARD:
            _set_constraint_mute(rig, REVERSE_CONSTRAINT, True)
            synced = _build_forward_constraints(source, rig)
            msg = f"Forward: rigify drives source ({synced} synced bones)"
        else:
            source.data['cp77_forward_sync_enabled'] = False
            built = 0
            has_any_reverse = any(
                pb.constraints.get(REVERSE_CONSTRAINT) is not None
                for pb in rig.pose.bones
            )
            if not has_any_reverse:
                built = _build_reverse_constraints(source, rig)
            _clear_forward_constraints(source)
            unmuted = _set_constraint_mute(rig, REVERSE_CONSTRAINT, False)
            tag = f", built {built}" if built else ''
            msg = f"Reverse: source drives rigify ({unmuted} bones{tag})"

        source.data['cp77_constraint_direction'] = direction
    finally:
        restore_previous_context()

    return True, msg


# The main converter.

class RigifyConverter:
    """Builds a Rigify metarig from a CP77 deform rig and generates the control rig."""

    def __init__(self, source_armature: bpy.types.Object):
        if not source_armature or source_armature.type != 'ARMATURE':
            raise ValueError('Valid armature required')
        self.source = source_armature
        self.meta: Optional[bpy.types.Object] = None
        self.rig: Optional[bpy.types.Object] = None
        self.stats = defaultdict(int)
        self.source_collections = list(getattr(source_armature, 'users_collection', []) or [])

    def log(self, msg: str, lvl: str = 'INFO'):
        symbols = {'INFO': '✓', 'WARN': '⚠', 'ERROR': '✗', 'STEP': '➡'}
        print(f"  {symbols.get(lvl, '•')} {msg}")

    def convert(self) -> bpy.types.Object:
        self.log(f"Converting '{self.source.name}'", 'STEP')
        store_current_context()
        try:
            existing_meta = get_metarig(self.source)
            existing_rig_name = self.source.data.get('cp77_rigify_rig')
            existing_rig = bpy.data.objects.get(existing_rig_name) if existing_rig_name else None

            if existing_meta is not None:
                self.meta = existing_meta
                self.log(f"Reusing metarig '{self.meta.name}'")
            else:
                self._create_metarig()
                self._prepare_metarig()

            self._generate_rigify(existing_rig=existing_rig)
            self._link_metadata()
            self._bind_forward_constraints()
            self._hide_metarig()
            return self.rig
        except Exception as e:
            self.log(f"FAILED: {e}", 'ERROR')
            self._cleanup_on_failure()
            raise
        finally:
            restore_previous_context()

    def _create_metarig(self) -> None:
        self.log('Creating metarig', 'STEP')
        src = self.source
        meta_obj = src.copy()
        meta_obj.data = src.data.copy()
        meta_obj.animation_data_clear()
        meta_obj.name = f"{src.name}_metarig"
        meta_obj.data.name = meta_obj.name

        if self.source_collections:
            for c in self.source_collections:
                try:
                    c.objects.link(meta_obj)
                except Exception:
                    pass
        else:
            bpy.context.scene.collection.objects.link(meta_obj)

        self.meta = meta_obj
        select_objects(self.meta)

    def _prepare_metarig(self) -> None:
        self.log('Preparing metarig', 'STEP')
        select_objects(self.meta)
        arm = self.meta.data

        safe_mode_switch('EDIT')
        eb = arm.edit_bones
        self._prune_deform_bones(eb)
        self._rename_bones(eb)
        self._build_chains(eb)
        self._build_finger_chains(eb)
        self._align_finger_rolls(eb)
        self._build_foot_chains(eb)
        self._reparent_weapons(eb)
        self._configure_colors(arm)
        self._configure_collections(arm, eb)

        safe_mode_switch('POSE')
        self._assign_rigify_types()
        self._configure_limb_parameters()
        self._strip_custom_shapes()

        safe_mode_switch('OBJECT')

    def _prune_deform_bones(self, eb) -> None:
        """Remove the CP77 deform bones from the metarig.
        """
        allowed = set(CP77_TO_METARIG.keys())
        to_remove = [b for b in eb if b.name not in allowed]
        for b in to_remove:
            eb.remove(b)

        self.stats['pruned_unmapped'] = len(to_remove)
        if to_remove:
            self.log(f"Pruned {len(to_remove)} unmapped source bones from metarig")

    def _rename_bones(self, eb) -> None:
        """Two-pass rename to avoid collisions with bones whose target name matches another bone."""
        TEMP = '__CP77T__'
        present = {b.name: b for b in eb}
        rename_map = {cp77: meta for cp77, meta in CP77_TO_METARIG.items() if cp77 in present}

        for cp77 in rename_map:
            present[cp77].name = TEMP + rename_map[cp77]

        present = {b.name: b for b in eb}
        for cp77, meta in rename_map.items():
            tagged = TEMP + meta
            if tagged in present:
                present[tagged].name = meta

        self.stats['renamed'] = len(rename_map)

    def _build_chains(self, eb) -> None:
        present = {b.name: b for b in eb}
        for chain in CHAINS:
            if not all(n in present for n in chain):
                continue
            for parent_name, child_name in zip(chain[:-1], chain[1:]):
                parent, child = present[parent_name], present[child_name]
                child.parent = parent
                parent.tail = child.head.copy()
                child.use_connect = True

    def _iter_source_meshes(self):
        seen = set()
        for obj in bpy.context.scene.objects:
            if obj.type != 'MESH' or obj.name in seen:
                continue
            if obj.parent == self.source:
                seen.add(obj.name)
                yield obj
                continue
            for mod in obj.modifiers:
                if mod.type == 'ARMATURE' and mod.object == self.source:
                    seen.add(obj.name)
                    yield obj
                    break

    def _weighted_terminal_cap(self,
                               cp77_bone: str,
                               tip_head: Vector,
                               direction: Vector,
                               max_distance: float) -> Optional[Vector]:
        """Estimate the anatomical fingertip center from the distal weight cap """
        if direction.length <= 1e-6:
            return None
        direction = direction.normalized()

        samples = []
        try:
            meta_inv = _safe_matrix_inverse(self.meta.matrix_world)
        except Exception:
            meta_inv = Matrix.Identity(4)

        for mesh in self._iter_source_meshes():
            group = mesh.vertex_groups.get(cp77_bone)
            if group is None:
                continue
            group_index = group.index
            mesh_world = mesh.matrix_world
            for vertex in mesh.data.vertices:
                weight = 0.0
                for assignment in vertex.groups:
                    if assignment.group == group_index:
                        weight = assignment.weight
                        break
                if weight <= 1e-4:
                    continue

                point = meta_inv @ (mesh_world @ vertex.co)
                offset = point - tip_head
                distance = offset.length
                if distance <= 1e-6 or distance > max_distance:
                    continue

                projection = offset.dot(direction)
                if projection <= 1e-5 or projection > max_distance:
                    continue

                lateral = offset - (direction * projection)
                # Reject broad stray assignments that are clearly not part of the fingertip
                if lateral.length > max(max_distance * 0.45, 0.04):
                    continue

                samples.append((projection, weight, point))

        if not samples:
            return None

        max_projection = max(p for p, _, _ in samples)
        if max_projection <= 1e-5:
            return None

        # Use only the far cap, not the whole distal phalanx envelope. The cap
        # depth scales with the last segment so small fingers and thumbs both
        # get stable centering.
        cap_depth = min(max(max_projection * 0.20, 0.01), 0.04)
        cap_min = max_projection - cap_depth
        cap = [(p, w, pt) for p, w, pt in samples if p >= cap_min]
        if not cap:
            cap = [max(samples, key=lambda item: item[0])]

        total = sum(max(w, 1e-4) for _, w, _ in cap)
        if total <= 1e-8:
            return None

        center = Vector((0.0, 0.0, 0.0))
        for _, weight, point in cap:
            center += point * max(weight, 1e-4)
        center /= total

        offset = center - tip_head
        projection = offset.dot(direction)
        if projection <= 1e-5 or projection > max_distance:
            return None

        # Keep the endpoint close to the actual cap center, but clamp excessive
        # sideways motion so one bad vertex group cannot aim the Rigify chain off
        # the finger. This is especially important for thumbs.
        lateral = offset - (direction * projection)
        max_lateral = max(projection * 0.35, 0.025)
        if lateral.length > max_lateral:
            lateral = lateral.normalized() * max_lateral

        return tip_head + (direction * projection) + lateral

    def _source_terminal_tail(self,
                              cp77_bone: str,
                              tip,
                              prev) -> Optional[Vector]:
        incoming = tip.head - prev.head
        imported = tip.tail - tip.head

        if incoming.length <= 1e-6:
            return None

        incoming_dir = incoming.normalized()
        max_distance = max(incoming.length * 4.0, 0.25)

        mesh_tail = self._weighted_terminal_cap(cp77_bone, tip.head, incoming_dir, max_distance)
        if mesh_tail is not None:
            self.stats['finger_tip_mesh_caps'] += 1
            return mesh_tail

        if imported.length > 1e-5:
            self.stats['finger_tip_imported_tails_rejected'] += 1
        self.stats['finger_tip_axis_fallbacks'] += 1
        return tip.head + incoming_dir * incoming.length

    def _build_finger_chains(self, eb) -> None:
        """Build Rigify finger chains with geometry-derived distal endpoints."""
        present = {b.name: b for b in eb}
        palm_for_chain = {
            'thumb': 'palm.01',
            'f_index': 'palm.02',
            'f_middle': 'palm.03',
            'f_ring': 'palm.04',
            'f_pinky': 'palm.05',
        }
        rebuilt = 0
        tips_preserved = 0
        tips_rebuilt = 0

        for side in ('L', 'R'):
            for chain in METARIG_FINGER_CHAINS[side]:
                bones = [present.get(n) for n in chain]
                if any(b is None for b in bones):
                    continue

                tip = bones[-1]
                prev = bones[-2] if len(bones) > 1 else None
                cp77_tip = METARIG_TO_CP77.get(tip.name)
                original_tail = tip.tail.copy()

                prefix = chain[0].split('.')[0]
                palm_base = palm_for_chain.get(prefix)
                palm = present.get(f'{palm_base}.{side}') if palm_base else None
                if palm is not None:
                    bones[0].parent = palm
                    bones[0].use_connect = False

                for parent, child in zip(bones[:-1], bones[1:]):
                    parent.tail = child.head.copy()
                    child.parent = parent
                    child.use_connect = True
                    rebuilt += 1

                if prev is None or cp77_tip is None:
                    continue

                # Fit the generated Rigify endpoint to the weighted fingertip cap
                tail = self._source_terminal_tail(cp77_tip, tip, prev)
                if tail is None:
                    tip.tail = original_tail
                    continue

                tip.tail = tail
                if (tip.tail - original_tail).length <= 1e-5:
                    tips_preserved += 1
                else:
                    tips_rebuilt += 1

        self.stats['finger_chains_rebuilt'] = rebuilt
        self.stats['finger_tips_preserved'] = tips_preserved
        self.stats['finger_tips_rebuilt'] = tips_rebuilt


    def _metarig_palm_normal(self, present, side) -> Optional[Vector]:
        """Palm-plane normal from the four-finger spread, used as a roll fallback."""
        def head(name):
            b = present.get(name)
            return b.head.copy() if b is not None else None

        index = head(f'f_index.01.{side}')
        pinky = head(f'f_pinky.01.{side}')
        mid_base = head(f'f_middle.01.{side}')
        mid_tip = head(f'f_middle.03.{side}')
        if any(v is None for v in (index, pinky, mid_base, mid_tip)):
            return None
        across = pinky - index
        forward = mid_tip - mid_base
        if across.length <= 1e-5 or forward.length <= 1e-5:
            return None
        normal = across.cross(forward)
        return normal.normalized() if normal.length > 1e-5 else None

    def _thumb_roll_target(self, present, side) -> Optional[Vector]:
        """Opposition-plane reference for the thumb.

        The thumb bends roughly perpendicular to the four-finger plane, so the
        palm normal is the wrong reference. Use the across-palm vector toward the
        middle finger base, projected off the thumb axis, as the palmar/curl
        direction
        """
        thumb = present.get(f'thumb.01.{side}')
        mid = present.get(f'f_middle.01.{side}')
        if thumb is None or mid is None:
            return None
        bone_dir = thumb.tail - thumb.head
        toward_palm = mid.head - thumb.head
        if bone_dir.length <= 1e-5 or toward_palm.length <= 1e-5:
            return None
        perp = toward_palm - toward_palm.project(bone_dir)
        return perp if perp.length > 1e-5 else None

    def _align_finger_rolls(self, eb) -> None:
        """Align finger phalanx roll so flexion resolves to the local X axis.

        After the chain tails are rewired the CP77 roll scalar no longer reflects
        a usable bend plane, so super_finger's automatic axis detection picks an
        off-axis result and fingers splay instead of curl. Each finger is rolled
        to its own rest bend plane (the palmar component of the distal segment),
        which keeps the bend axis consistent across both hands without relying on
        mirror assumptions. Must run after _build_finger_chains so distal bones have a
        geometry-derived direction to roll.
        """
        present = {b.name: b for b in eb}
        aligned = 0
        for side in ('L', 'R'):
            fallback = self._metarig_palm_normal(present, side)
            for chain in METARIG_FINGER_CHAINS[side]:
                bones = [present[n] for n in chain if n in present]
                if len(bones) < 2:
                    continue

                if chain[0].startswith('thumb'):
                    z_ref = self._thumb_roll_target(present, side)
                elif len(bones) >= 3:
                    s1 = bones[1].head - bones[0].head
                    s2 = bones[2].head - bones[1].head
                    if s1.length > 1e-5 and s2.length > 1e-5:
                        z_ref = s2 - s2.project(s1)
                    else:
                        z_ref = None
                else:
                    z_ref = None

                if z_ref is None or z_ref.length <= 1e-5:
                    z_ref = fallback
                if z_ref is None or z_ref.length <= 1e-5:
                    continue

                z_ref = z_ref.normalized()
                for b in bones:
                    b.align_roll(z_ref)
                    aligned += 1
        self.stats['finger_rolls_aligned'] = aligned

    def _build_foot_chains(self, eb) -> None:
        present = {b.name: b for b in eb}
        for side in ('.L', '.R'):
            foot = present.get(f'foot{side}')
            heel = present.get(f'heel{side}')
            toe  = present.get(f'toe{side}')
            if not (foot and heel and toe):
                continue
                
            foot_head = foot.head.copy()
            heel_head = heel.head.copy()
            toe_head = toe.head.copy()
            
            heel.parent = foot
            heel.use_connect = False
            heel.head = heel_head

            toe.parent = foot
            foot.tail = toe_head
            toe.use_connect = True

            heel_axis = toe_head - heel_head
            if heel_axis.length <= 1e-4:
                heel_axis = foot_head - heel_head
            if heel_axis.length > 1e-4:
                heel.tail = heel_head + heel_axis.normalized() * min(max(heel_axis.length * 0.5, 0.04), 0.10)

            toe_forward = toe_head - heel_head
            if toe_forward.length <= 1e-4:
                toe_forward = toe_head - foot_head
            if toe_forward.length <= 1e-4:
                toe_forward = foot.tail - foot.head

            if toe_forward.length > 1e-4:
                toe_len = min(max(toe_forward.length * 0.45, 0.06), 0.12)
                toe.tail = toe.head + toe_forward.normalized() * toe_len

    def _reparent_weapons(self, eb) -> None:
        """Pin weapon controls to their hand parents and give them a useful tail length.

        Source weapon bones have zero-length tails which Rigify rejects.
        """
        present = {b.name: b for b in eb}
        for side in ('L', 'R'):
            weapon = present.get(f'weapon.{side}')
            hand   = present.get(f'hand.{side}')
            if not (weapon and hand):
                continue
            weapon.parent = hand
            weapon.use_connect = False
            if (weapon.tail - weapon.head).length < 1e-4:
                offset = (hand.tail - hand.head)
                weapon.tail = weapon.head + (offset * 0.5 if offset.length > 1e-4
                                             else (0.0, 0.05, 0.0))

    def _configure_colors(self, arm) -> None:
        if not hasattr(arm, 'rigify_colors'):
            return
        while arm.rigify_colors:
            arm.rigify_colors.remove(arm.rigify_colors[0])
        for name, active, normal in COLOR_SETS:
            c = arm.rigify_colors.add()
            c.name = name
            c.active = Color(active)
            c.normal = Color(normal)
            c.select = Color(SELECT_COLOR)
            c.standard_colors_lock = True

    def _configure_collections(self, arm, eb) -> None:
        if not hasattr(arm, 'collections'):
            return
        while arm.collections:
            arm.collections.remove(arm.collections[0])
        present = {b.name: b for b in eb}
        for name, (members, row, color_id) in COLLECTIONS.items():
            coll = arm.collections.new(name=name)
            set_rigify_coll_prop(coll, 'rigify_ui_row', row)
            set_rigify_coll_prop(coll, 'rigify_color_set_id', color_id)
            for bn in members:
                b = present.get(bn)
                if b is not None:
                    coll.assign(b)

    def _assign_rigify_types(self) -> None:
        pb = {b.name: b for b in self.meta.pose.bones}
        for name, rtype in RIGIFY_TYPES.items():
            target = pb.get(name)
            if target is not None:
                target.rigify_type = rtype

    def _configure_limb_parameters(self) -> None:
        pb = {b.name: b for b in self.meta.pose.bones}
        for side in ('L', 'R'):
            for limb in (f'thigh.{side}', f'upper_arm.{side}'):
                b = pb.get(limb)
                if b is None:
                    continue
                params = b.rigify_parameters
                params.rotation_axis = 'automatic'
                params.segments = 2
                params.limb_uniform_scale = True
                if params.foot_pivot_type and params.foot_pivot_type == 'ANKLE_TOE':
                    params.extra_ik_toe = True
                    params.ik_local_location = True
                
            for finger in ('thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01'):
                b = pb.get(f'{finger}.{side}')
                if b is not None:
                    b.rigify_parameters.primary_rotation_axis = 'automatic'

    def _strip_custom_shapes(self) -> None:
        for b in self.meta.pose.bones:
            b.custom_shape = None

    def _generate_rigify(self, existing_rig: Optional[bpy.types.Object] = None) -> None:
        self.log('Generating Rigify rig', 'STEP')
        select_objects(self.meta)
        safe_mode_switch('POSE')

        if existing_rig is not None and existing_rig.type == 'ARMATURE':
            self.meta.data.rigify_target_rig = existing_rig
            self.log(f"Updating existing rig '{existing_rig.name}' in place")

        if not hasattr(bpy.ops.pose, 'rigify_generate'):
            raise RuntimeError('Rigify addon not enabled (pose.rigify_generate missing).')

        objs_before = set(bpy.data.objects)
        bpy.ops.pose.rigify_generate()

        if existing_rig is not None and existing_rig.name in bpy.data.objects:
            self.rig = existing_rig
        else:
            new_objs = [o for o in (set(bpy.data.objects) - objs_before) if o.type == 'ARMATURE']
            self.rig = new_objs[0] if new_objs else None

        if not self.rig:
            raise RuntimeError('Rigify generation failed to produce an armature')
        self.log(f"Generated '{self.rig.name}'")

        # Match the rig's scene-collection placement to the source.
        for coll in list(self.rig.users_collection):
            try:
                coll.objects.unlink(self.rig)
            except Exception:
                pass
        if self.source_collections:
            for coll in self.source_collections:
                try:
                    coll.objects.link(self.rig)
                except Exception:
                    pass
        else:
            bpy.context.scene.collection.objects.link(self.rig)

        self._post_process_rigify()

    def _post_process_rigify(self) -> None:
        select_objects(self.rig)
        safe_mode_switch('POSE')
        for b in self.rig.pose.bones:
            if 'IK_Stretch' in b.keys():
                b['IK_Stretch'] = 0.0
        self.stats['neutralized_controls'] = _neutralize_rigify_controls(self.rig)

        safe_mode_switch('EDIT')
        arm = self.rig.data
        fk = arm.collections.get('FK') or arm.collections.new('FK')
        ik = arm.collections.get('IK') or arm.collections.new('IK')
        tw = arm.collections.get('Tweak') or arm.collections.new('Tweak')
        set_rigify_coll_prop(fk, 'rigify_color_set_id', 5)
        set_rigify_coll_prop(fk, 'rigify_ui_row', 8)
        set_rigify_coll_prop(ik, 'rigify_color_set_id', 2)
        set_rigify_coll_prop(ik, 'rigify_ui_row', 8)
        set_rigify_coll_prop(tw, 'rigify_color_set_id', 4)
        set_rigify_coll_prop(tw, 'rigify_ui_row', 9)

        for b in arm.edit_bones:
            nl = b.name.lower()
            if '_fk' in nl:
                target = fk
            elif '_ik' in nl and '_parent' not in nl:
                target = ik
            elif 'tweak' in nl:
                target = tw
            else:
                target = None
            if target is None:
                continue
            for c in tuple(b.collections):
                c.unassign(b)
            target.assign(b)
            self.stats[f'{target.name.lower()}_controls'] += 1

        safe_mode_switch('POSE')

    def _bind_forward_constraints(self) -> None:
        self.log('Binding forward matrix-basis sync (rigify → source)', 'STEP')
        n = _build_forward_constraints(self.source, self.rig, recapture_neutral=True)
        self.stats['source_sync_bones'] = n
        safe_mode_switch('OBJECT')

    def _link_metadata(self) -> None:
        """Cross-link the trio so downstream operators can navigate any-to-any."""
        self.source.data['cp77_metarig']     = self.meta.name
        self.source.data['cp77_rigify_rig']  = self.rig.name
        self.source.data['cp77_rig_id']      = self.rig.data.get('rig_id', '')
        self.source.data['cp77_constraint_direction'] = DIRECTION_FORWARD
        self.meta.data['cp77_source_rig']    = self.source.name
        self.rig.data['cp77_source_rig']     = self.source.name

    def _hide_metarig(self) -> None:
        try:
            self.meta.hide_set(True)
            self.meta.hide_viewport = True
        except Exception:
            pass

    def _cleanup_on_failure(self) -> None:
        for obj in (self.rig, self.meta):
            try:
                if obj and obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass


def cp77_to_rigify() -> Optional[bpy.types.Object]:
    """Convert the active armature to Rigify."""
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE':
        print('ERROR: Select an armature')
        return None
    return RigifyConverter(obj).convert()


if __name__ == '__main__':
    cp77_to_rigify()
