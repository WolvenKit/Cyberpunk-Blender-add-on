import math
import struct


FRAME_TIMES_ARRAY_SIZE = 200


def _f32(value):
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]


DEFAULT_FRAME_TIME = _f32(0.014)
_MAX_INPUT_FRAME_TIME = _f32(0.2)
_SMOOTHING_PERIOD = _f32(0.25)
_PAUSE_FRAME_TIME = _f32(0.0001)
_HALF = _f32(0.5)


class AverageFrameTimeCalculator:
    __slots__ = ('frame_times', 'average_frame_time')

    def __init__(self):
        self.frame_times = [DEFAULT_FRAME_TIME] * FRAME_TIMES_ARRAY_SIZE
        self.average_frame_time = _f32(0.0)

    def recalculate(self, new_frame_time):
        value = _f32(new_frame_time)
        if not math.isfinite(value):
            value = _f32(0.0)
        clamped_frame_time = min(
            _MAX_INPUT_FRAME_TIME, max(_f32(0.0), value)
        )

        self.frame_times[1:] = self.frame_times[:-1]
        self.frame_times[0] = clamped_frame_time

        frame_count = 1
        if self.average_frame_time != 0.0:
            ratio = _f32(_SMOOTHING_PERIOD / self.average_frame_time)
            frame_count = int(_f32(ratio + _HALF))
            frame_count = min(
                FRAME_TIMES_ARRAY_SIZE, max(1, frame_count)
            )

        average = _f32(0.0)
        for index in range(frame_count):
            average = _f32(average + self.frame_times[index])
        self.average_frame_time = _f32(average / _f32(frame_count))
        if clamped_frame_time < _PAUSE_FRAME_TIME:
            self.average_frame_time = clamped_frame_time
        return self.average_frame_time

    def reset(self):
        self.frame_times[:] = [DEFAULT_FRAME_TIME] * FRAME_TIMES_ARRAY_SIZE
        self.average_frame_time = _f32(0.0)
