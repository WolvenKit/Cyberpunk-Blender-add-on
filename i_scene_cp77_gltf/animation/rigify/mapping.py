from __future__ import annotations
from typing import Dict, Iterable, List, Optional, Tuple

# CP77 source bones mapped to Rigify human metarig names.
CP77_TO_METARIG: Dict[str, str] = {
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


# Rigify generator type assignments.
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


# Metarig connectivity applied before Rigify generation.
CHAINS: List[List[str]] = [
    ['pelvis', 'spine', 'spine.001', 'spine.002', 'spine.003'],
    ['spine.004', 'spine.005', 'spine.006'],
]
for _s in ('L', 'R'):
    CHAINS.append([f'thigh.{_s}', f'shin.{_s}', f'foot.{_s}'])
    CHAINS.append([f'upper_arm.{_s}', f'forearm.{_s}', f'hand.{_s}'])


# Per-side finger chains used for endpoint repair and roll alignment.
METARIG_FINGER_CHAINS: Dict[str, Tuple[Tuple[str, ...], ...]] = {}
for _s in ('L', 'R'):
    METARIG_FINGER_CHAINS[_s] = (
        (f'thumb.01.{_s}', f'thumb.02.{_s}'),
        tuple(f'f_index.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_middle.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_ring.0{_j}.{_s}' for _j in range(1, 4)),
        tuple(f'f_pinky.0{_j}.{_s}' for _j in range(1, 4)),
    )


# Bone collection layout: name -> (members, UI row, color set).
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


# Rigify color sets in generator order.
COLOR_SETS: List[Tuple[str, Tuple[float, float, float], Tuple[float, float, float]]] = [
    ('Root',    (0.549, 1.000, 1.000), (0.435, 0.184, 0.416)),
    ('IK',      (0.549, 1.000, 1.000), (0.604, 0.000, 0.000)),
    ('Special', (0.549, 1.000, 1.000), (0.957, 0.788, 0.047)),
    ('Tweak',   (0.549, 1.000, 1.000), (0.039, 0.212, 0.580)),
    ('FK',      (0.549, 1.000, 1.000), (0.118, 0.569, 0.035)),
    ('Extra',   (0.549, 1.000, 1.000), (0.969, 0.251, 0.094)),
]

SELECT_COLOR: Tuple[float, float, float] = (0.314, 0.784, 1.000)


# Direction flags and deterministic constraint names.
FORWARD_CONSTRAINT: str = 'CP77_RigifyDrivesSource'
REVERSE_CONSTRAINT: str = 'CP77_SourceDrivesRigify'

DIRECTION_FORWARD: str = 'forward'
DIRECTION_REVERSE: str = 'reverse'

# Limit forward-sync translation to deform-safe CP77 joints.
FORWARD_LOCATION_BONES = {'Root', 'Hips'}
FORWARD_LIMITED_LOCATION_BONES = {'LeftHand', 'RightHand', 'LeftFoot', 'RightFoot'}
LIMITED_LOCATION_OFFSETS = {
    'LeftHand': 0.35,
    'RightHand': 0.35,
    'LeftFoot': 1.25,
    'RightFoot': 1.25,
}
MAX_LIMITED_LOCATION_OFFSET = 0.35

# Neutralize Rigify controls that do not map 1:1 to CP77 deform joints.
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


# Forward-sync constraint names cleared before matrix-basis sync.
FORWARD_CONSTRAINT_NAMES = (
    FORWARD_CONSTRAINT,
    f'{FORWARD_CONSTRAINT}Location',
    'CP77_SourcePoseSyncBridge',
)


# Prefix for evaluated Rigify neutral matrices stored on the source armature.
FORWARD_NEUTRAL_PROP_PREFIX = 'cp77_forward_neutral_'


# Reverse sync targets FK controls where Rigify exposes them.
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


def resolve_forward_target(cp77_bone: str, metarig_bone: str,
                            rig_bone_names: set) -> Optional[str]:
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
        # Sample generated deform bones, not visible super-finger controls.
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


def set_rigify_coll_prop(coll, name: str, value) -> None:
    try:
        setattr(coll, name, value)
    except (AttributeError, TypeError):
        coll[name] = value


def get_rigify_coll_prop(coll, name: str, default=0):
    if hasattr(coll, name):
        return getattr(coll, name)
    return coll.get(name, default)

def reverse_target_for(cp77_bone: str, metarig_bone: Optional[str],
                        rig_bone_names: set) -> Optional[str]:
    explicit = CP77_TO_RIGIFY_REVERSE.get(cp77_bone)
    if explicit and explicit in rig_bone_names:
        return explicit
    if metarig_bone is not None:
        return _resolve_target(rig_bone_names, metarig_bone)
    return None
