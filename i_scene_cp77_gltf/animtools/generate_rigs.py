from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Optional, Tuple

import bpy
from mathutils import Color

from ..main.bartmoss_functions import (
    restore_previous_context, safe_mode_switch, select_objects, store_current_context,
    )

# CP77 source bone  →  metarig bone (Rigify human metarig naming)
CP77_TO_METARIG: Dict[str, str] = {
    'Root': 'root',
    'Hips': 'pelvis',
    'Spine': 'spine',
    'Spine1': 'spine.001',
    'Spine2': 'spine.002',
    'Spine3': 'spine.003',
    'Neck': 'spine.004',
    'Neck1': 'spine.005',
    'Head': 'spine.006',
    'LeftEye': 'eye.L',
    'RightEye': 'eye.R',

    'LeftUpLeg': 'thigh.L',
    'LeftLeg': 'shin.L',
    'LeftFoot': 'foot.L',
    'LeftHeel': 'heel.L',
    'LeftToeBase': 'toe.L',
    'RightUpLeg': 'thigh.R',
    'RightLeg': 'shin.R',
    'RightFoot': 'foot.R',
    'RightHeel': 'heel.R',
    'RightToeBase': 'toe.R',

    'LeftShoulder': 'shoulder.L',
    'LeftArm': 'upper_arm.L',
    'LeftForeArm': 'forearm.L',
    'LeftHand': 'hand.L',
    'WeaponLeft': 'weapon.L',
    'RightShoulder': 'shoulder.R',
    'RightArm': 'upper_arm.R',
    'RightForeArm': 'forearm.R',
    'RightHand': 'hand.R',
    'WeaponRight': 'weapon.R',

    'LeftInHandThumb': 'palm.01.L',
    'LeftHandThumb1': 'thumb.01.L',
    'LeftHandThumb2': 'thumb.02.L',
    'LeftInHandIndex': 'palm.02.L',
    'LeftHandIndex1': 'f_index.01.L',
    'LeftHandIndex2': 'f_index.02.L',
    'LeftHandIndex3': 'f_index.03.L',
    'LeftInHandMiddle': 'palm.03.L',
    'LeftHandMiddle1': 'f_middle.01.L',
    'LeftHandMiddle2': 'f_middle.02.L',
    'LeftHandMiddle3': 'f_middle.03.L',
    'LeftInHandRing': 'palm.04.L',
    'LeftHandRing1': 'f_ring.01.L',
    'LeftHandRing2': 'f_ring.02.L',
    'LeftHandRing3': 'f_ring.03.L',
    'LeftInHandPinky': 'palm.05.L',
    'LeftHandPinky1': 'f_pinky.01.L',
    'LeftHandPinky2': 'f_pinky.02.L',
    'LeftHandPinky3': 'f_pinky.03.L',

    'RightInHandThumb': 'palm.01.R',
    'RightHandThumb1': 'thumb.01.R',
    'RightHandThumb2': 'thumb.02.R',
    'RightInHandIndex': 'palm.02.R',
    'RightHandIndex1': 'f_index.01.R',
    'RightHandIndex2': 'f_index.02.R',
    'RightHandIndex3': 'f_index.03.R',
    'RightInHandMiddle': 'palm.03.R',
    'RightHandMiddle1': 'f_middle.01.R',
    'RightHandMiddle2': 'f_middle.02.R',
    'RightHandMiddle3': 'f_middle.03.R',
    'RightInHandRing': 'palm.04.R',
    'RightHandRing1': 'f_ring.01.R',
    'RightHandRing2': 'f_ring.02.R',
    'RightHandRing3': 'f_ring.03.R',
    'RightInHandPinky': 'palm.05.R',
    'RightHandPinky1': 'f_pinky.01.R',
    'RightHandPinky2': 'f_pinky.02.R',
    'RightHandPinky3': 'f_pinky.03.R',
    }

METARIG_TO_CP77: Dict[str, str] = {v: k for k, v in CP77_TO_METARIG.items()}

# Metarig bone  →  rigify_type assignment
RIGIFY_TYPES: Dict[str, str] = {
    'pelvis': 'spines.basic_spine',
    'spine.004': 'spines.super_head',
    'shoulder.L': 'basic.super_copy',
    'shoulder.R': 'basic.super_copy',
    'eye.L': 'basic.super_copy',
    'eye.R': 'basic.super_copy',
    'thigh.L': 'limbs.leg',
    'thigh.R': 'limbs.leg',
    'upper_arm.L': 'limbs.super_limb',
    'upper_arm.R': 'limbs.super_limb',
    'weapon.L': 'basic.super_copy',
    'weapon.R': 'basic.super_copy',
    }
for _side in ('L', 'R'):
    for _finger in ('thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01'):
        RIGIFY_TYPES[f'{_finger}.{_side}'] = 'limbs.super_finger'
    for _i in range(1, 6):
        RIGIFY_TYPES[f'palm.0{_i}.{_side}'] = 'basic.super_copy'

# Parent / connect chains for the metarig prep pass
CHAINS: List[List[str]] = [
    ['pelvis', 'spine', 'spine.001', 'spine.002', 'spine.003'],
    ['spine.004', 'spine.005', 'spine.006'],
    ]
for _s in ('L', 'R'):
    CHAINS.append([f'thigh.{_s}', f'shin.{_s}', f'foot.{_s}'])
    CHAINS.append([f'upper_arm.{_s}', f'forearm.{_s}', f'hand.{_s}'])
    CHAINS.append([f'palm.01.{_s}', f'thumb.01.{_s}', f'thumb.02.{_s}'])
    for _i, _f in [(2, 'f_index'), (3, 'f_middle'), (4, 'f_ring'), (5, 'f_pinky')]:
        CHAINS.append(
                [f'palm.0{_i}.{_s}'] + [f'{_f}.0{_j}.{_s}' for _j in range(1, 4)]
                )

# Bone collection layout: name → (members, row, color_set_id)
COLLECTIONS: Dict[str, Tuple[List[str], int, int]] = {
    'Root': (['root', 'pelvis'], 0, 1),
    'Torso': (['spine', 'spine.001', 'spine.002', 'spine.003'], 3, 5),
    'Face': (['spine.004', 'spine.005', 'spine.006', 'eye.L', 'eye.R'], 2, 3),
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
    ('Root', (0.549, 1.000, 1.000), (0.435, 0.184, 0.416)),
    ('IK', (0.549, 1.000, 1.000), (0.604, 0.000, 0.000)),
    ('Special', (0.549, 1.000, 1.000), (0.957, 0.788, 0.047)),
    ('Tweak', (0.549, 1.000, 1.000), (0.039, 0.212, 0.580)),
    ('FK', (0.549, 1.000, 1.000), (0.118, 0.569, 0.035)),
    ('Extra', (0.549, 1.000, 1.000), (0.969, 0.251, 0.094)),
    ]

SELECT_COLOR: Tuple[float, float, float] = (0.314, 0.784, 1.000)

# Constraint naming. Both directions use identifiable names so we can
# locate/mute/unmute them deterministically.
FORWARD_CONSTRAINT: str = 'CP77_RigifyDrivesSource'
REVERSE_CONSTRAINT: str = 'CP77_SourceDrivesRigify'

DIRECTION_FORWARD: str = 'forward'
DIRECTION_REVERSE: str = 'reverse'

# CP77 bone  →  preferred Rigify target for the *reverse* direction.
# Rigify FK controls where they exist, falling through to the same lookup
# as forward direction for bones without an FK split.
CP77_TO_RIGIFY_REVERSE: Dict[str, str] = {
    'Hips': 'torso',
    'Spine': 'spine_fk',
    'Spine1': 'spine_fk.001',
    'Spine2': 'spine_fk.002',
    'Spine3': 'spine_fk.003',
    'Head': 'head',
    'LeftEye': 'eye.L',
    'RightEye': 'eye.R',

    'LeftShoulder': 'shoulder.L',
    'LeftArm': 'upper_arm_fk.L',
    'LeftForeArm': 'forearm_fk.L',
    'LeftHand': 'hand_fk.L',
    'RightShoulder': 'shoulder.R',
    'RightArm': 'upper_arm_fk.R',
    'RightForeArm': 'forearm_fk.R',
    'RightHand': 'hand_fk.R',

    'LeftUpLeg': 'thigh_fk.L',
    'LeftLeg': 'shin_fk.L',
    'LeftFoot': 'foot_fk.L',
    'LeftToeBase': 'toe_fk.L',
    'RightUpLeg': 'thigh_fk.R',
    'RightLeg': 'shin_fk.R',
    'RightFoot': 'foot_fk.R',
    'RightToeBase': 'toe_fk.R',
    }


def _resolve_target(rig_bone_names: set, base: str) -> Optional[str]:
    """Locate the bone on the rigify rig that best represents *base*.

    Order: DEF- → ORG- → MCH- → bare name. Used for forward constraints and as
    the fallback for reverse-direction lookups when no explicit FK control is
    specified in CP77_TO_RIGIFY_REVERSE.
    """
    for cand in (f'DEF-{base}', f'ORG-{base}', f'MCH-{base}', base):
        if cand in rig_bone_names:
            return cand
    return None


def set_rigify_coll_prop(coll, name: str, value) -> None:
    """Write a Rigify bone-collection property across Blender versions.

    Pre-4.3 Blender exposed ``rigify_ui_row`` / ``rigify_color_set_id`` /
    ``rigify_ui_title`` as RNA attributes on BoneCollection; from 4.3 onward
    Rigify stores them as ID properties read via ``coll.get(name)``. Try the
    attribute path first and fall back to bracket assignment so the same code
    works on both.
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


def _reverse_target_for(
        cp77_bone: str, metarig_bone: Optional[str],
        rig_bone_names: set,
        ) -> Optional[str]:
    """Pick the rigify target bone used when source drives rigify."""
    explicit = CP77_TO_RIGIFY_REVERSE.get(cp77_bone)
    if explicit and explicit in rig_bone_names:
        return explicit
    if metarig_bone is not None:
        return _resolve_target(rig_bone_names, metarig_bone)
    return None


# Public pair-lookup helpers used by the UI 

def find_pair(
        obj: Optional[bpy.types.Object],
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


# Constraint plumbing.

def _make_copy_transforms(
        bone: bpy.types.PoseBone, name: str,
        target: bpy.types.Object, subtarget: str,
        ) -> bpy.types.Constraint:
    """Create or refresh a named COPY_TRANSFORMS constraint at the end of the stack."""
    existing = bone.constraints.get(name)
    if existing is not None:
        bone.constraints.remove(existing)
    c = bone.constraints.new('COPY_TRANSFORMS')
    c.name = name
    c.target = target
    c.subtarget = subtarget
    c.target_space = 'LOCAL_OWNER_ORIENT'
    c.owner_space = 'LOCAL'
    if hasattr(c, 'use_offset'):
        c.use_offset = False
    if hasattr(c, 'mix_mode'):
        c.mix_mode = 'REPLACE'
    return c


def _set_constraint_mute(
        armature_obj: bpy.types.Object,
        constraint_name: str, mute: bool,
        ) -> int:
    """Mute or unmute every same-named constraint on the rig. Returns count."""
    n = 0
    for pb in armature_obj.pose.bones:
        c = pb.constraints.get(constraint_name)
        if c is not None:
            c.mute = mute
            n += 1
    return n


def _build_forward_constraints(
        source: bpy.types.Object,
        rig: bpy.types.Object,
        ) -> int:
    """Place COPY_TRANSFORMS on source bones, targeting the rigify rig."""
    rig_bone_names = set(rig.data.bones.keys())
    select_objects(source)
    safe_mode_switch('POSE')
    n = 0
    for pb in source.pose.bones:
        meta = CP77_TO_METARIG.get(pb.name)
        if not meta:
            continue
        sub = _resolve_target(rig_bone_names, meta)
        if not sub:
            continue
        _make_copy_transforms(pb, FORWARD_CONSTRAINT, rig, sub)
        n += 1
    return n


def _build_reverse_constraints(
        source: bpy.types.Object,
        rig: bpy.types.Object,
        ) -> int:
    """Place COPY_TRANSFORMS on rigify control bones, targeting the source rig.

    Lazy-created on first reverse-direction toggle; thereafter persists muted.
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


def set_constraint_direction(
        source: bpy.types.Object,
        rig: bpy.types.Object,
        direction: str,
        ) -> Tuple[bool, str]:
    """Toggle which side drives which. Creates the reverse-side constraints lazily."""
    if direction not in (DIRECTION_FORWARD, DIRECTION_REVERSE):
        return False, f"Unknown direction '{direction}'"
    if source is None or rig is None:
        return False, 'Missing source or rigify rig'

    store_current_context()
    try:
        if direction == DIRECTION_FORWARD:
            _set_constraint_mute(rig, REVERSE_CONSTRAINT, True)
            unmuted = _set_constraint_mute(source, FORWARD_CONSTRAINT, False)
            msg = f"Forward: rigify drives source ({unmuted} bones)"
        else:
            built = 0
            has_any_reverse = any(
                    pb.constraints.get(REVERSE_CONSTRAINT) is not None
                    for pb in rig.pose.bones
                    )
            if not has_any_reverse:
                built = _build_reverse_constraints(source, rig)
            _set_constraint_mute(source, FORWARD_CONSTRAINT, True)
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
        self._rename_bones(eb)
        self._build_chains(eb)
        self._build_foot_chains(eb)
        self._reparent_weapons(eb)
        self._configure_colors(arm)
        self._configure_collections(arm, eb)

        safe_mode_switch('POSE')
        self._assign_rigify_types()
        self._configure_limb_parameters()
        self._strip_custom_shapes()

        safe_mode_switch('OBJECT')

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

    def _build_foot_chains(self, eb) -> None:
        present = {b.name: b for b in eb}
        for side in ('.L', '.R'):
            foot = present.get(f'foot{side}')
            heel = present.get(f'heel{side}')
            toe = present.get(f'toe{side}')
            if not (foot and heel and toe):
                continue
            heel.parent = foot
            toe.parent = foot
            foot.tail = heel.head.copy()
            heel.tail = toe.head.copy()
            heel.use_connect = False
            toe.use_connect = True

    def _reparent_weapons(self, eb) -> None:
        """Pin weapon controls to their hand parents and give them a useful tail length.

        Source weapon bones often have zero-length tails which Rigify rejects.
        """
        present = {b.name: b for b in eb}
        for side in ('L', 'R'):
            weapon = present.get(f'weapon.{side}')
            hand = present.get(f'hand.{side}')
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
                params.rotation_axis = 'x'
                params.segments = 2
                params.limb_uniform_scale = False
            for finger in ('thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01'):
                b = pb.get(f'{finger}.{side}')
                if b is not None:
                    b.rigify_parameters.primary_rotation_axis = 'X'

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
        self.log('Binding forward constraints (rigify → source)', 'STEP')
        n = _build_forward_constraints(self.source, self.rig)
        self.stats['source_constraints'] = n
        safe_mode_switch('OBJECT')

    def _link_metadata(self) -> None:
        """Cross-link the trio so downstream operators can navigate any-to-any."""
        self.source.data['cp77_metarig'] = self.meta.name
        self.source.data['cp77_rigify_rig'] = self.rig.name
        self.source.data['cp77_rig_id'] = self.rig.data.get('rig_id', '')
        self.source.data['cp77_constraint_direction'] = DIRECTION_FORWARD
        self.meta.data['cp77_source_rig'] = self.source.name
        self.rig.data['cp77_source_rig'] = self.source.name

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
