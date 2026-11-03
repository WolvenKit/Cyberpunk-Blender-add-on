from __future__ import annotations


def source_clip_sample_frame(
    time_seconds: float,
    *,
    frame_start: float,
    frame_end: float,
    clip_front: float,
    clip_end: float,
    fps: float,
    looped: bool,
) -> float:
    clip_front = max(0.0, float(clip_front))
    clip_end = max(0.0, float(clip_end))
    start = float(frame_start) + clip_front * float(fps)
    end = max(start, float(frame_end) - clip_end * float(fps))
    sample = float(frame_start) + float(time_seconds) * float(fps)
    if not looped or end <= start:
        return max(start, min(end, sample))

    span = end - start
    if sample > end:
        remainder = (sample - end) % span
        return end if remainder == 0.0 else start + remainder
    if sample < start:
        remainder = (start - sample) % span
        return start if remainder == 0.0 else end - remainder
    return sample


def mixer_entry_sample_frame(
    master_frame: float,
    *,
    master_origin: float,
    frame_start: float,
    frame_end: float,
    time_offset_seconds: float = 0.0,
    time_scale: float = 1.0,
    fps: float = 30.0,
    master_fps: float | None = None,
    looped: bool = False,
) -> float:
    fps = float(fps)
    master_fps = fps if master_fps is None else float(master_fps)
    if fps <= 0.0 or master_fps <= 0.0:
        raise ValueError("animation sampling FPS must be positive")
    time_seconds = float(time_offset_seconds) + (
        (float(master_frame) - float(master_origin)) / master_fps
    ) * float(time_scale)
    return source_clip_sample_frame(
        time_seconds,
        frame_start=frame_start,
        frame_end=frame_end,
        clip_front=0.0,
        clip_end=0.0,
        fps=fps,
        looped=bool(looped),
    )


def advance_source_clip_time(
    current_time: float,
    time_step: float,
    *,
    clip_front: float,
    clip_end_time: float,
    looped: bool,
) -> tuple[float, bool]:
    start = float(clip_front)
    end = max(start, float(clip_end_time))
    span = end - start
    current = float(current_time)
    step = float(time_step)
    next_time = current + step
    ended = False
    if looped and span > 0.0:
        if step > 0.0 and next_time >= end:
            ended = True
            while next_time > end:
                next_time -= span
        elif step < 0.0 and next_time < start:
            ended = True
            while next_time < start:
                next_time += span
        return next_time, ended
    if next_time >= end:
        ended = step > 0.0 or current >= end
        return end, ended
    if next_time < start:
        ended = step < 0.0
        return start, ended
    return next_time, ended


def one_shot_weight(
    time_seconds: float, duration: float, blend_in: float, blend_out: float
) -> float:
    """Weight of a one-shot clip over its input pose"""
    time_seconds = float(time_seconds)
    duration = float(duration)
    if time_seconds > duration:
        return 0.0
    if time_seconds < float(blend_in):
        return time_seconds / float(blend_in)
    if duration - time_seconds < float(blend_out):
        return (duration - time_seconds) / float(blend_out)
    return 1.0


def clip_events_passed(
    events,
    previous_time: float,
    next_time: float,
    *,
    frame_start: float,
    fps: float,
    clip_front: float,
    clip_end_time: float,
    wrapped: bool = False,
    first: bool = False,
) -> set[str]:
    """Names of the clip events passed playing from previous_time to next_time"""
    previous, current = float(previous_time), float(next_time)
    front, end = float(clip_front), float(clip_end_time)
    if wrapped and current <= previous:
        stretches = ((previous, end, first), (front, current, True))
    elif wrapped:
        stretches = ((front, previous, True), (current, end, True))
    elif current >= previous:
        stretches = ((previous, current, first),)
    else:
        stretches = ((current, previous, True),)
    fired = set()
    for event in events:
        name = str(event.get("eventName", "") or "")
        if not name or name == "None":
            continue
        start = (
            float(event.get("startFrame", frame_start) or 0.0) - float(frame_start)
        ) / float(fps)
        length = max(0.0, float(event.get("durationInFrames", 0.0) or 0.0)) / float(fps)
        for low, high, closed in stretches:
            if length > 0.0:
                overlaps = start <= high and (
                    start + length >= low if closed else start + length > low
                )
            else:
                overlaps = (low <= start if closed else low < start) and start <= high
            if overlaps:
                fired.add(name)
                break
    return fired
