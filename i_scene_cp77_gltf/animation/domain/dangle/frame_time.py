import math

from ....bartmoss.single import f32

FRAME_TIMES_ARRAY_SIZE = 200
MIN_FRAME_TIME = 0.001
MAX_FRAME_TIME = 0.1
MAX_TIME_STEPS = 15

DEFAULT_FRAME_TIME = f32(0.014)
_MAX_INPUT_FRAME_TIME = f32(0.2)
_SMOOTHING_PERIOD = f32(0.25)
_PAUSE_FRAME_TIME = f32(0.0001)
_HALF = f32(0.5)


class SmoothedFrameTime:
    __slots__ = ("average_frame_time", "frame_times")

    def __init__(self):
        self.frame_times = [DEFAULT_FRAME_TIME] * FRAME_TIMES_ARRAY_SIZE
        self.average_frame_time = f32(0.0)

    def recalculate(self, new_frame_time):
        value = f32(new_frame_time)
        if not math.isfinite(value):
            value = f32(0.0)
        clamped_frame_time = min(_MAX_INPUT_FRAME_TIME, max(f32(0.0), value))

        self.frame_times[1:] = self.frame_times[:-1]
        self.frame_times[0] = clamped_frame_time

        frame_count = 1
        if self.average_frame_time != 0.0:
            ratio = f32(_SMOOTHING_PERIOD / self.average_frame_time)
            frame_count = int(f32(ratio + _HALF))
            frame_count = min(FRAME_TIMES_ARRAY_SIZE, max(1, frame_count))

        average = f32(0.0)
        for index in range(frame_count):
            average = f32(average + self.frame_times[index])
        self.average_frame_time = f32(average / f32(frame_count))
        if clamped_frame_time < _PAUSE_FRAME_TIME:
            self.average_frame_time = clamped_frame_time
        return self.average_frame_time

    def reset(self):
        self.frame_times[:] = [DEFAULT_FRAME_TIME] * FRAME_TIMES_ARRAY_SIZE
        self.average_frame_time = f32(0.0)


def fixed_rate_steps(average_frame_time, simulation_fps):
    """(substep time, substep count) for one smoothed frame at simulation_fps"""
    frame_time = (
        min(MAX_FRAME_TIME, max(MIN_FRAME_TIME, average_frame_time))
        if abs(average_frame_time) > 0.00001
        else 0.0
    )
    steps = max(1, min(MAX_TIME_STEPS, int(math.ceil(frame_time * simulation_fps))))
    return frame_time / steps, steps
