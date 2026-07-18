import math
from enum import IntEnum

import numpy as np

from .frame_time import AverageFrameTimeCalculator


class _OvershootState(IntEnum):
    FREE_MOVEMENT = 0
    GOING_TO_OVERSHOOT = 1
    IN_OVERSHOOT = 2

class DragPostProcessor:
    def __init__(self, sim):
        self.sim = sim
        state = sim.state

        source_indices = []
        target_indices = []
        fps_list = []
        speed_mult = []
        has_overshoot = []
        os_min_speed = []
        os_max_speed = []
        os_duration = []
        use_steps = []
        steps_speed_mult = []
        time_between = []
        time_in = []
        config_indices = []

        for config_index, dn in enumerate(state.drag_nodes):
            source_name = dn.source_bone_name or dn.bone_name
            source_idx = sim.resolve_bone_index(source_name)
            target_idx = sim.resolve_bone_index(dn.bone_name)
            if source_idx is None or target_idx is None:
                continue
            config_indices.append(config_index)
            source_indices.append(source_idx)
            target_indices.append(target_idx)
            fps_list.append(max(1.0, dn.simulation_fps))
            speed_mult.append(max(0.001, dn.source_speed_multiplier))
            has_overshoot.append(bool(dn.has_overshoot))
            os_min_speed.append(max(0.0, dn.overshoot_detection_min_speed))
            os_max_speed.append(
                max(dn.overshoot_detection_min_speed + 0.001,
                    dn.overshoot_detection_max_speed)
            )
            os_duration.append(max(0.001, dn.overshoot_duration))
            use_steps.append(bool(getattr(dn, 'use_steps', False)))
            steps_speed_mult.append(
                float(getattr(dn, 'steps_target_speed_multiplier', 10000.0))
            )
            time_between.append(
                float(getattr(dn, 'time_between_steps', 0.1))
            )
            time_in.append(float(getattr(dn, 'time_in_step', 0.1)))

        self.num_drags = len(target_indices)
        self.source_indices = np.asarray(source_indices, dtype=np.int32)
        self.drag_indices = np.asarray(target_indices, dtype=np.int32)
        self.config_indices = np.asarray(config_indices, dtype=np.int32)
        self.config_to_runtime = {
            int(config_index): runtime_index
            for runtime_index, config_index in enumerate(self.config_indices)
        }
        if self.num_drags == 0:
            return

        self.drag_fps = np.array(fps_list, dtype=np.float32)
        self.speed_mult = np.array(speed_mult, dtype=np.float32)

        self.has_overshoot = np.array(has_overshoot, dtype=bool)
        self.os_min_speed = np.array(os_min_speed, dtype=np.float32)
        self.os_max_speed = np.array(os_max_speed, dtype=np.float32)
        self.os_duration = np.array(os_duration, dtype=np.float32)

        self.use_steps = np.array(use_steps, dtype=bool)
        self.steps_speed_mult = np.array(steps_speed_mult, dtype=np.float32)
        self.time_between = np.array(time_between, dtype=np.float32)
        self.time_in = np.array(time_in, dtype=np.float32)

        n = self.num_drags

        self.source_pos = np.zeros((n, 3), dtype=np.float32)
        self.target_pos = np.zeros((n, 3), dtype=np.float32)
        self.last_frame_target_bone_pos = np.zeros((n, 3), dtype=np.float32)

        self.overshoot_state = np.full(n, _OvershootState.FREE_MOVEMENT, dtype=np.int32)
        self.can_overshoot = np.ones(n, dtype=bool)
        self.initial_overshoot_vel = np.zeros((n, 3), dtype=np.float32)
        self.time_left_to_start_overshoot = np.zeros(n, dtype=np.float32)
        self.overshoot_timer = np.zeros(n, dtype=np.float32)

        self.stopped_target_queue = [[] for _ in range(n)]

        self.step_timer = np.zeros(n, dtype=np.float32)

        self.frame_time_calculators = [
            AverageFrameTimeCalculator() for _ in range(n)
        ]

        self._initialized = np.zeros(n, dtype=bool)

    def reset(self):
        if self.num_drags == 0:
            return
        source_bone_pos = np.asarray([
            self._bone_position(int(index)) for index in self.source_indices
        ], dtype=np.float32)
        target_bone_pos = self._current_target_positions()
        self.source_pos[:] = source_bone_pos
        self.target_pos[:] = target_bone_pos
        self.last_frame_target_bone_pos[:] = target_bone_pos
        self.overshoot_state[:] = _OvershootState.FREE_MOVEMENT
        self.can_overshoot[:] = True
        self.initial_overshoot_vel[:] = 0.0
        self.time_left_to_start_overshoot[:] = 0.0
        self.overshoot_timer[:] = 0.0
        self.stopped_target_queue = [[] for _ in range(self.num_drags)]
        self.step_timer[:] = 0.0
        self.frame_time_calculators = [
            AverageFrameTimeCalculator() for _ in range(self.num_drags)
        ]
        self._initialized[:] = True

    def step(self, raw_dt):
        if self.num_drags == 0:
            return
        for runtime_index in range(self.num_drags):
            self.step_runtime(runtime_index, raw_dt)

    def step_runtime(self, runtime_index, raw_dt):
        if not 0 <= runtime_index < self.num_drags:
            return

        this_frame_bone_pos = self._bone_position(
            int(self.drag_indices[runtime_index])
        )
        if not self._initialized[runtime_index]:
            self.source_pos[runtime_index] = self._bone_position(
                int(self.source_indices[runtime_index])
            )
            self.target_pos[runtime_index] = this_frame_bone_pos
            self.last_frame_target_bone_pos[runtime_index] = (
                this_frame_bone_pos
            )
            self.can_overshoot[runtime_index] = True
            self.stopped_target_queue[runtime_index] = []
            self.overshoot_state[runtime_index] = (
                _OvershootState.FREE_MOVEMENT
            )
            self.step_timer[runtime_index] = 0.0
            self._initialized[runtime_index] = True
            return

        self._step_single(runtime_index, raw_dt, this_frame_bone_pos)
        self.last_frame_target_bone_pos[runtime_index] = this_frame_bone_pos

    def _bone_position(self, tracked_index):
        bone_name = self.sim.bone_names[tracked_index]
        pose_bone = self.sim.arm_obj.pose.bones.get(bone_name)
        if pose_bone is None:
            return np.zeros(3, dtype=np.float32)
        return np.asarray(pose_bone.matrix.translation, dtype=np.float32)

    def _current_target_positions(self):
        return np.asarray([
            self._bone_position(int(index)) for index in self.drag_indices
        ], dtype=np.float32)

    def _step_single(self, di, raw_dt, this_frame_bone_pos):
        calculator = self.frame_time_calculators[di]
        calculator.recalculate(raw_dt)
        avg_dt = calculator.average_frame_time

        if abs(avg_dt) < 0.00001:
            return
        avg_dt = max(0.001, min(avg_dt, 0.1))

        sim_fps = self.drag_fps[di]
        time_steps_count = max(1, min(15, math.ceil(avg_dt * sim_fps)))
        dt = avg_dt / time_steps_count

        last_bone_pos = self.last_frame_target_bone_pos[di]

        for step_idx in range(time_steps_count):
            frame_progress = (step_idx + 1.0) / time_steps_count
            lerped_bone_pos = last_bone_pos + (this_frame_bone_pos - last_bone_pos) * frame_progress

            prev_target = self.target_pos[di].copy()
            self._update_target_position(di, lerped_bone_pos, dt)
            self._detect_new_overshoot(di, prev_target, dt)
            self._update_source_position(di, dt)

    def _update_target_position(self, di, bone_pos, dt):
        if self.use_steps[di]:
            pending_dt = dt
            while pending_dt > 0.0:
                timer = self.step_timer[di]
                tb = self.time_between[di]
                ti = self.time_in[di]

                if 0.0 <= timer < tb:
                    consumed = min(tb - timer, pending_dt)
                    pending_dt -= consumed
                    self.step_timer[di] += consumed

                    diff = bone_pos - self.target_pos[di]
                    dist = np.linalg.norm(diff)
                    if dist > 1e-8:
                        speed = self.steps_speed_mult[di] * math.sqrt(dist)
                        travel = speed * consumed
                        if travel >= dist:
                            self.target_pos[di] = bone_pos.copy()
                        else:
                            self.target_pos[di] += diff * (travel / dist)

                elif tb <= timer < tb + ti:
                    consumed = min(tb + ti - timer, pending_dt)
                    pending_dt -= consumed
                    self.step_timer[di] += consumed
                else:
                    self.step_timer[di] = 0.0
        else:
            self.target_pos[di] = bone_pos.copy()

    def _detect_new_overshoot(self, di, prev_target, dt):
        if not self.has_overshoot[di] or dt <= 0.0:
            return

        target = self.target_pos[di]
        target_speed = np.linalg.norm(target - prev_target) / dt

        if target_speed > self.os_max_speed[di] and not self.can_overshoot[di]:
            self.can_overshoot[di] = True
        elif target_speed < self.os_min_speed[di] and self.can_overshoot[di]:
            self.can_overshoot[di] = False

            added = self._add_stopped_target(di, target)
            if not added:
                return

            state = self.overshoot_state[di]

            if state == _OvershootState.FREE_MOVEMENT:
                vel = self._calc_free_velocity(di)
                speed = np.linalg.norm(vel)
                self.initial_overshoot_vel[di] = vel
                if speed > 0.0:
                    self.overshoot_state[di] = _OvershootState.GOING_TO_OVERSHOOT
                    dist_to_target = np.linalg.norm(
                        target - self.source_pos[di]
                    )
                    self.time_left_to_start_overshoot[di] = dist_to_target / speed
                else:
                    self.overshoot_state[di] = _OvershootState.IN_OVERSHOOT
                    self.overshoot_timer[di] = 0.0

            elif state == _OvershootState.GOING_TO_OVERSHOOT:
                self.overshoot_state[di] = _OvershootState.IN_OVERSHOOT
                self.overshoot_timer[di] = 0.0

    def _update_source_position(self, di, dt):
        pending_dt = dt

        while pending_dt > 0.0:
            state = self.overshoot_state[di]

            if state == _OvershootState.FREE_MOVEMENT:
                diff = self.target_pos[di] - self.source_pos[di]
                dist = np.linalg.norm(diff)
                vel = self._calc_free_velocity(di)
                travel = vel * pending_dt
                travel_dist = np.linalg.norm(travel)
                if travel_dist >= dist:
                    self.source_pos[di] = self.target_pos[di].copy()
                else:
                    self.source_pos[di] += travel
                pending_dt = 0.0

            elif state == _OvershootState.GOING_TO_OVERSHOOT:
                time_left = self.time_left_to_start_overshoot[di]
                if time_left <= pending_dt:
                    consumed = time_left
                    self.time_left_to_start_overshoot[di] = 0.0
                    pending_dt -= consumed
                else:
                    consumed = pending_dt
                    self.time_left_to_start_overshoot[di] -= pending_dt
                    pending_dt = 0.0

                self.source_pos[di] += self.initial_overshoot_vel[di] * consumed

                if self.time_left_to_start_overshoot[di] == 0.0:
                    self.overshoot_state[di] = _OvershootState.IN_OVERSHOOT
                    self.overshoot_timer[di] = 0.0

            elif state == _OvershootState.IN_OVERSHOOT:
                duration = self.os_duration[di]
                timer = self.overshoot_timer[di]

                if timer + pending_dt >= duration:
                    consumed = duration - timer
                    self.overshoot_timer[di] = duration
                    pending_dt -= consumed
                else:
                    consumed = pending_dt
                    self.overshoot_timer[di] += pending_dt
                    pending_dt = 0.0

                t = self.overshoot_timer[di] / duration
                blend_weight = t * t * (3.0 - 2.0 * t)

                free_vel = self._calc_free_velocity(di)
                cached_vel = self.initial_overshoot_vel[di]
                blended_vel = cached_vel + (free_vel - cached_vel) * blend_weight
                self.source_pos[di] += blended_vel * consumed

                if self.overshoot_timer[di] >= duration:
                    queue = self.stopped_target_queue[di]
                    if queue:
                        queue.pop(0)

                    if not queue:
                        self.overshoot_state[di] = _OvershootState.FREE_MOVEMENT
                    else:
                        vel = self._calc_free_velocity(di)
                        speed = np.linalg.norm(vel)
                        self.initial_overshoot_vel[di] = vel
                        if speed > 0.0:
                            self.overshoot_state[di] = _OvershootState.GOING_TO_OVERSHOOT
                            dist_to_target = np.linalg.norm(
                                self.target_pos[di] - self.source_pos[di]
                            )
                            self.time_left_to_start_overshoot[di] = (
                                dist_to_target / speed
                            )
                        else:
                            self.overshoot_state[di] = _OvershootState.IN_OVERSHOOT
                            self.overshoot_timer[di] = 0.0

            else:
                pending_dt = 0.0

    def _calc_free_velocity(self, di):
        diff = self.target_pos[di] - self.source_pos[di]
        dist = np.linalg.norm(diff)
        if dist < 1e-8:
            return np.zeros(3, dtype=np.float32)
        return diff * (self.speed_mult[di] * math.sqrt(dist) / dist)

    def _add_stopped_target(self, di, target_pos):
        queue = self.stopped_target_queue[di]

        if len(queue) >= 2:
            queue.pop()

        if not queue or np.linalg.norm(queue[0] - target_pos) > 1e-6:
            queue.append(target_pos.copy())
            return True
        return False