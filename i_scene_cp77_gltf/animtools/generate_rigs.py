import bpy
from mathutils import Color
from collections import defaultdict
from ..main.bartmoss_functions import (
    store_current_context,
    restore_previous_context,
    safe_mode_switch,
    select_objects
)

class RigifyConverter:
    """Optimized Rigify converter with minimal mode switching and efficient operations."""

    BONE_MAP = {
        'root': 'Root', 'pelvis': 'Hips', 'spine': 'Spine', 'spine.001': 'Spine1',
        'spine.002': 'Spine2', 'spine.003': 'Spine3', 'spine.004': 'Neck', 'spine.005': 'Neck1',
        'spine.006': 'Head', 'eye.L': 'LeftEye', 'eye.R': 'RightEye', 'thigh.L': 'LeftUpLeg',
        'shin.L': 'LeftLeg', 'foot.L': 'LeftFoot', 'heel.L': 'LeftHeel', 'toe.L': 'LeftToeBase',
        'thigh.R': 'RightUpLeg', 'shin.R': 'RightLeg', 'foot.R': 'RightFoot', 'heel.R': 'RightHeel',
        'toe.R': 'RightToeBase', 'shoulder.L': 'LeftShoulder', 'upper_arm.L': 'LeftArm',
        'forearm.L': 'LeftForeArm', 'hand.L': 'LeftHand', 'shoulder.R': 'RightShoulder',
        'upper_arm.R': 'RightArm', 'forearm.R': 'RightForeArm', 'hand.R': 'RightHand',
        'palm.01.L': 'LeftInHandThumb', 'thumb.01.L': 'LeftHandThumb1', 'thumb.02.L': 'LeftHandThumb2',
        'palm.02.L': 'LeftInHandIndex', 'f_index.01.L': 'LeftHandIndex1', 'f_index.02.L': 'LeftHandIndex2',
        'f_index.03.L': 'LeftHandIndex3', 'palm.03.L': 'LeftInHandMiddle', 'f_middle.01.L': 'LeftHandMiddle1',
        'f_middle.02.L': 'LeftHandMiddle2', 'f_middle.03.L': 'LeftHandMiddle3', 'palm.04.L': 'LeftInHandRing',
        'f_ring.01.L': 'LeftHandRing1', 'f_ring.02.L': 'LeftHandRing2', 'f_ring.03.L': 'LeftHandRing3',
        'palm.05.L': 'LeftInHandPinky', 'f_pinky.01.L': 'LeftHandPinky1', 'f_pinky.02.L': 'LeftHandPinky2',
        'f_pinky.03.L': 'LeftHandPinky3', 'palm.01.R': 'RightInHandThumb', 'thumb.01.R': 'RightHandThumb1',
        'thumb.02.R': 'RightHandThumb2', 'palm.02.R': 'RightInHandIndex', 'f_index.01.R': 'RightHandIndex1',
        'f_index.02.R': 'RightHandIndex2', 'f_index.03.R': 'RightHandIndex3', 'palm.03.R': 'RightInHandMiddle',
        'f_middle.01.R': 'RightHandMiddle1', 'f_middle.02.R': 'RightHandMiddle2', 'f_middle.03.R': 'RightHandMiddle3',
        'palm.04.R': 'RightInHandRing', 'f_ring.01.R': 'RightHandRing1', 'f_ring.02.R': 'RightHandRing2',
        'f_ring.03.R': 'RightHandRing3', 'palm.05.R': 'RightInHandPinky', 'f_pinky.01.R': 'RightHandPinky1',
        'f_pinky.02.R': 'RightHandPinky2', 'f_pinky.03.R': 'RightHandPinky3'
    }

    RIGIFY_TYPES = {
        "pelvis": "spines.basic_spine", "spine.004": "spines.super_head",
        **{f"{b}.{s}": "basic.super_copy" for b in ["shoulder", "eye"] for s in ['L', 'R']},
        **{f"thigh.{s}": "limbs.leg" for s in ['L', 'R']},
        **{f"upper_arm.{s}": "limbs.super_limb" for s in ['L', 'R']},
        **{f"{b}.{s}": "limbs.super_finger" for b in ["thumb.01", "f_index.01", "f_middle.01", "f_ring.01", "f_pinky.01"] for s in ['L', 'R']},
        **{f"palm.0{i}.{s}": "basic.super_copy" for i in range(1, 6) for s in ['L', 'R']}
    }

    # Pre-compute chains for alignment
    CHAINS = [
        ["pelvis", "spine", "spine.001", "spine.002", "spine.003"],
        ["spine.004", "spine.005", "spine.006"],
        *[[f"{b}.{s}" for b in ["thigh", "shin", "foot"]] for s in ['L', 'R']],
        *[[f"{b}.{s}" for b in ["upper_arm", "forearm", "hand"]] for s in ['L', 'R']],
        *[[f"palm.01.{s}", f"thumb.01.{s}", f"thumb.02.{s}"] for s in ['L', 'R']],
        *[[f"palm.0{i}.{s}"] + [f"{f}.0{j}.{s}" for j in range(1, 4)] for i, f in [(2, "f_index"), (3, "f_middle"), (4, "f_ring"), (5, "f_pinky")] for s in ['L', 'R']]
    ]

    # Collection definitions
    COLLECTIONS = {
        "Root": (['root', 'pelvis'], 0, 1),
        "Torso": (['spine', 'spine.001', 'spine.002', 'spine.003'], 3, 5),
        "Face": (['spine.004', 'spine.005', 'spine.006', 'eye.L', 'eye.R'], 2, 3),
        **{f"Arms.{s}": ([f"{b}.{s}" for b in ['shoulder', 'upper_arm', 'forearm', 'hand']], 3, 5) for s in ['L', 'R']},
        **{f"Legs.{s}": ([f"{b}.{s}" for b in ['thigh', 'shin', 'foot', 'heel', 'toe']], 4, 5) for s in ['L', 'R']},
        **{f"Fingers.{s}": (
            [f"palm.0{i}.{s}" for i in range(1, 6)] +
            [f"thumb.0{i}.{s}" for i in range(1, 3)] +
            [f"{f}.0{j}.{s}" for f in ['f_index', 'f_middle', 'f_ring', 'f_pinky'] for j in range(1, 4)],
            4, 4
        ) for s in ['L', 'R']}
    }

    def __init__(self, source_armature):
        if not source_armature or source_armature.type != 'ARMATURE':
            raise ValueError("Valid armature required")
        self.source = source_armature
        self.meta = None
        self.rig = None
        self.stats = defaultdict(int)
        self.inverse_map = {v: k for k, v in self.BONE_MAP.items()}
        self.source_collections = list(getattr(source_armature, "users_collection", []) or [])

    def log(self, msg, lvl="INFO"):
        symbols = {'INFO': '✓', 'WARN': '⚠', 'ERROR': '✗', 'STEP': '➡️'}
        print(f"  {symbols.get(lvl, '•')} {msg}")

    def convert(self):
        self.log(f"Converting '{self.source.name}'", "STEP")
        store_current_context()
        try:
            self.create_metarig()
            self.prepare_metarig()
            self.generate_and_finalize()
            return self.rig
        except Exception as e:
            self.log(f"FAILED: {e}", "ERROR")
            self.cleanup()
            raise
        finally:
            restore_previous_context()

    def create_metarig(self):
        self.log("Creating metarig", "STEP")
        src = self.source
        meta_obj = src.copy()
        meta_obj.data = src.data.copy()
        meta_obj.animation_data_clear()
        meta_obj.name = f"{src.name}_metarig"
        meta_obj.data.name = meta_obj.name
        if self.source_collections:
            for c in self.source_collections:
                try: c.objects.link(meta_obj)
                except Exception: pass
        else:
            bpy.context.scene.collection.objects.link(meta_obj)
        self.meta = meta_obj
        select_objects(self.meta)

    def prepare_metarig(self):
        self.log("Preparing metarig", "STEP")
        select_objects(self.meta)
        arm = self.meta.data

        safe_mode_switch('EDIT')
        eb = arm.edit_bones
        eb_dict = {b.name: b for b in eb}
        rename_map = {v: k for k, v in self.BONE_MAP.items() if v in eb_dict}
        temp = "__T__"
        for old in list(rename_map.keys()):
            b = eb_dict.get(old)
            if b: b.name = f"{temp}{rename_map[old]}"
        eb_dict = {b.name: b for b in eb}
        for old, new in rename_map.items():
            tagged = f"{temp}{new}"
            b = eb_dict.get(tagged)
            if b: b.name = new
        self.stats['renamed'] = len(rename_map)

        eb_dict = {b.name: b for b in eb}

        # Parent/connect chains
        for chain in self.CHAINS:
            if all(n in eb_dict for n in chain):
                for p_name, c_name in zip(chain[:-1], chain[1:]):
                    p, c = eb_dict[p_name], eb_dict[c_name]
                    c.parent = p
                    p.tail = c.head.copy()
                    c.use_connect = True

        # Foot > heel/toe parenting
        for side in ('.L', '.R'):
            foot, heel, toe = f'foot{side}', f'heel{side}', f'toe{side}'
            f, h, t = eb_dict.get(foot), eb_dict.get(heel), eb_dict.get(toe)
            if f and h and t:
                h.parent = t.parent = f
                f.tail = h.head.copy()
                h.tail = t.head.copy()
                h.use_connect = False
                t.use_connect = True

        # Colours
        if hasattr(arm, "rigify_colors"):
            while arm.rigify_colors:
                arm.rigify_colors.remove(arm.rigify_colors[0])
            for name, active, normal in [
                ("Root", (0.549, 1.0, 1.0), (0.435, 0.184, 0.416)),
                ("IK", (0.549, 1.0, 1.0), (0.604, 0.0, 0.0)),
                ("Special", (0.549, 1.0, 1.0), (0.957, 0.788, 0.047)),
                ("Tweak", (0.549, 1.0, 1.0), (0.039, 0.212, 0.580)),
                ("FK", (0.549, 1.0, 1.0), (0.118, 0.569, 0.035)),
                ("Extra", (0.549, 1.0, 1.0), (0.969, 0.251, 0.094))
            ]:
                c = arm.rigify_colors.add()
                c.name, c.active, c.normal, c.select = name, Color(active), Color(normal), Color((0.314, 0.784, 1.0))
                c.standard_colors_lock = True

        # Bone collections
        if hasattr(arm, "collections"):
            while arm.collections:
                arm.collections.remove(arm.collections[0])
            for name, (bones, row, color) in self.COLLECTIONS.items():
                coll = arm.collections.new(name=name)
                coll.rigify_ui_row = row
                coll.rigify_color_set_id = color
                for bn in bones:
                    b = eb_dict.get(bn)
                    if b: coll.assign(b)

        safe_mode_switch('POSE')
        pb = self.meta.pose.bones
        pb_dict = {b.name: b for b in pb}

        for name, rtype in self.RIGIFY_TYPES.items():
            p = pb_dict.get(name)
            if p: p.rigify_type = rtype

        for s in ['L', 'R']:
            for limb in (f'thigh.{s}', f'upper_arm.{s}'):
                p = pb_dict.get(limb)
                if p:
                    prm = p.rigify_parameters
                    prm.rotation_axis = 'x'
                    prm.segments = 2
                    prm.limb_uniform_scale = False

        for s in ['.L', '.R']:
            for f in ['thumb.01', 'f_index.01', 'f_middle.01', 'f_ring.01', 'f_pinky.01']:
                p = pb_dict.get(f'{f}{s}')
                if p: p.rigify_parameters.primary_rotation_axis = 'X'

        for b in pb: b.custom_shape = None
        safe_mode_switch('OBJECT')

    def generate_and_finalize(self):
        self.log("Generating Rigify rig", "STEP")
        select_objects(self.meta)
        safe_mode_switch('POSE')

        objs_before = set(bpy.data.objects)
        if not hasattr(bpy.ops.pose, "rigify_generate"):
            raise RuntimeError("Rigify addon not enabled (pose.rigify_generate missing).")
        bpy.ops.pose.rigify_generate()

        new_objs = [o for o in (set(bpy.data.objects) - objs_before) if o.type == 'ARMATURE']
        self.rig = new_objs[0] if new_objs else None
        if not self.rig:
            raise RuntimeError("Rigify generation failed to produce an armature")
        self.log(f"Generated '{self.rig.name}'")

        # Collections
        for coll in list(self.rig.users_collection):
            try: coll.objects.unlink(self.rig)
            except Exception: pass
        if self.source_collections:
            for coll in self.source_collections:
                try: coll.objects.link(self.rig)
                except Exception: pass
        else:
            bpy.context.scene.collection.objects.link(self.rig)

        # Post-processing on rigify
        select_objects(self.rig)
        safe_mode_switch('POSE')
        for b in self.rig.pose.bones:
            if "IK_Stretch" in b.keys(): b["IK_Stretch"] = 0.0

        safe_mode_switch('EDIT')
        arm = self.rig.data
        fk = arm.collections.get("FK") or arm.collections.new("FK")
        ik = arm.collections.get("IK") or arm.collections.new("IK")
        tw = arm.collections.get("Tweak") or arm.collections.new("Tweak")
        fk.rigify_color_set_id, fk.rigify_ui_row = 5, 8
        ik.rigify_color_set_id, ik.rigify_ui_row = 2, 8
        tw.rigify_color_set_id, tw.rigify_ui_row = 4, 9

        for b in arm.edit_bones:
            nl = b.name.lower()
            target = fk if '_fk' in nl else (ik if ('_ik' in nl and '_parent' not in nl) else (tw if 'tweak' in nl else None))
            if target:
                for c in tuple(b.collections): c.unassign(b)
                target.assign(b)
                self.stats[f'{target.name.lower()}_controls'] += 1

        safe_mode_switch('POSE')

        self.log("Linking Rigify → Source (Copy Transforms on source bones)", "STEP")
        rig_bone_names = set(self.rig.data.bones.keys())
        inv = self.inverse_map  
        def best_target(base):
            for cand in (f"DEF-{base}", f"ORG-{base}", f"MCH-{base}", base):
                if cand in rig_bone_names:
                    return cand
            return None

        select_objects(self.source)
        safe_mode_switch('POSE')
        for s_bone in self.source.pose.bones:
            base = inv.get(s_bone.name)
            if not base:
                continue
            sub = best_target(base)
            if not sub:
                continue
            for c in list(s_bone.constraints):
                if c.type == 'COPY_TRANSFORMS' and c.name == "RigifyLink":
                    s_bone.constraints.remove(c)
            c = s_bone.constraints.new('COPY_TRANSFORMS')
            c.name = "RigifyLink"
            c.target = self.rig
            c.subtarget = sub
            c.target_space = 'LOCAL_OWNER_ORIENT'
            c.owner_space = 'LOCAL'
            if hasattr(c, "use_offset"): c.use_offset = False
            if hasattr(c, "mix_mode"): c.mix_mode = 'REPLACE'
            self.stats['source_constraints'] += 1
        safe_mode_switch('OBJECT')
        try:
            self.meta.hide_set(True)
            self.meta.hide_viewport = True
        except Exception:
            pass

    def cleanup(self):
        for obj in [self.rig, self.meta]:
            try:
                if obj and obj.name in bpy.data.objects:
                    bpy.data.objects.remove(obj, do_unlink=True)
            except Exception:
                pass


def cp77_to_rigify():
    """Convert the active armature to Rigify."""
    obj = bpy.context.active_object
    if not obj or obj.type != 'ARMATURE':
        print("ERROR: Select an armature")
        return None
    return RigifyConverter(obj).convert()


# for testing in the text editor
if __name__ == "__main__":
    cp77_to_rigify()
