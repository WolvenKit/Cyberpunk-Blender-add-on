from __future__ import annotations

from typing import Optional

from mathutils import Matrix, Vector

from ....animation.rigify.mapping import METARIG_FINGER_CHAINS, METARIG_TO_CP77
from .state import RigifyStage


def _safe_matrix_inverse(matrix):
    return matrix.inverted_safe() if hasattr(matrix, "inverted_safe") else matrix.inverted()


class FingerChainBuilder(RigifyStage):
    def build(self, edit_bones) -> None:
        self._build_finger_chains(edit_bones)
        self._align_finger_rolls(edit_bones)

    def _iter_source_meshes(self):
        seen = set()
        for obj in self.context.scene.objects:
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
                # Reject broad stray weights outside this terminal phalanx cap.
                if lateral.length > max(max_distance * 0.45, 0.04):
                    continue

                samples.append((projection, weight, point))

        if not samples:
            return None

        max_projection = max(p for p, _, _ in samples)
        if max_projection <= 1e-5:
            return None

        # Average only the far weighted cap to avoid pulling the endpoint inward.
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

        # Clamp lateral drift so bad weights cannot aim the chain off-finger.
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

        # Ignore Maya terminal tails; fall back to the previous phalanx axis.
        if imported.length > 1e-5:
            self.stats['finger_tip_imported_tails_rejected'] += 1
        self.stats['finger_tip_axis_fallbacks'] += 1
        return tip.head + incoming_dir * incoming.length

    def _build_finger_chains(self, eb) -> None:
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

                # Fit terminal endpoints to fingertip weights, then axis-fallback.
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
