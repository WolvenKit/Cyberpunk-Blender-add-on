from __future__ import annotations

import math
from dataclasses import dataclass

from ...assetio.transform_values import vector3_from_data
from ...assetio.values import cname_value, coerce_float
from ..common.entity_data import component_name

_AXIS_INDEX = {"X": 0, "Y": 1, "Z": 2}
_EPSILON = 1.0e-9


@dataclass(frozen=True, slots=True)
class TransformAnimatorSegment:
    axis_name: str
    axis_no: int
    start_seconds: float
    duration_seconds: float
    start_radians: float
    end_radians: float
    interpolation: str
    easing: str
    source_type: str


@dataclass(frozen=True, slots=True)
class TransformAnimatorMoveSegment:
    start_seconds: float
    duration_seconds: float
    start_offset: tuple[float, float, float]
    target_local_position: tuple[float, float, float]
    interpolation: str
    easing: str
    source_type: str


@dataclass(frozen=True, slots=True)
class TransformAnimatorProgram:
    name: str
    auto_start: bool
    looping: bool
    reverse: bool
    time_scale: float
    times_to_play: int
    duration_seconds: float
    segments: tuple[TransformAnimatorSegment, ...]
    move_segments: tuple[TransformAnimatorMoveSegment, ...]
    unsupported_items: tuple[str, ...]

    @property
    def axis_numbers(self) -> tuple[int, ...]:
        return tuple(sorted({segment.axis_no for segment in self.segments}))


@dataclass(frozen=True, slots=True)
class TransformAnimatorKey:
    seconds: float
    value: float
    interpolation: str
    easing: str = "AUTO"


def _positive_time_scale(value) -> float:
    scale = abs(coerce_float(value, 1.0, unwrap=False))
    return scale if scale > 1.0e-8 else 1.0


def _movement_interpolation(implementation):
    movement = (
        implementation.get("movement") if isinstance(implementation, dict) else None
    )
    movement_data = movement.get("Data") if isinstance(movement, dict) else None
    if not isinstance(movement_data, dict):
        return "LINEAR", "AUTO"
    function = movement_data.get("function")
    if not isinstance(function, dict):
        return "LINEAR", "AUTO"
    transition = str(function.get("transitionType") or "EET_Linear")
    easing = str(function.get("easingType") or "EET_InOut")
    interpolation_map = {
        "EET_Linear": "LINEAR",
        "EET_Back": "BACK",
        "EET_Bounce": "BOUNCE",
        "EET_Circular": "CIRC",
        "EET_Cubic": "CUBIC",
        "EET_Elastic": "ELASTIC",
        "EET_Exponential": "EXPO",
        "EET_Quad": "QUAD",
        "EET_Quadratic": "QUAD",
        "EET_Quartic": "QUART",
        "EET_Quintic": "QUINT",
        "EET_Sinusoidal": "SINE",
    }
    easing_map = {
        "EET_In": "EASE_IN",
        "EET_Out": "EASE_OUT",
        "EET_InOut": "EASE_IN_OUT",
    }
    return interpolation_map.get(transition, "LINEAR"), easing_map.get(easing, "AUTO")


def _track_implementation(item, anim_impl_lookup):
    impl = item.get("impl") if isinstance(item, dict) else None
    if not isinstance(impl, dict):
        return None
    inline = impl.get("Data")
    if isinstance(inline, dict):
        return inline
    handle_ref = impl.get("HandleRefId")
    if handle_ref is None:
        return None
    try:
        handle_ref = int(handle_ref)
    except (TypeError, ValueError):
        return None
    referenced = (anim_impl_lookup or {}).get(handle_ref)
    if isinstance(referenced, dict) and isinstance(referenced.get("Data"), dict):
        return referenced["Data"]
    return referenced if isinstance(referenced, dict) else None


def _handle_data(value):
    if not isinstance(value, dict):
        return None
    data = value.get("Data")
    return data if isinstance(data, dict) else None


def build_anim_impl_lookup(chunks):
    """Index every inline transform-animation implementation exposed by chunk data"""
    lookup = {}
    for chunk in chunks or ():
        if (
            not isinstance(chunk, dict)
            or chunk.get("$type") != "gameTransformAnimatorComponent"
        ):
            continue
        for animation in chunk.get("animations") or ():
            if not isinstance(animation, dict):
                continue
            timeline = animation.get("timeline")
            items = timeline.get("items") if isinstance(timeline, dict) else ()
            for item in items or ():
                impl = item.get("impl") if isinstance(item, dict) else None
                if not isinstance(impl, dict) or not isinstance(impl.get("Data"), dict):
                    continue
                handle_id = impl.get("HandleId")
                if handle_id is None:
                    continue
                try:
                    lookup[int(handle_id)] = impl["Data"]
                except (TypeError, ValueError):
                    continue
    return lookup


def _compile_rotation_segment(implementation, start_seconds, duration):
    axis_name = str(implementation.get("axis") or "X").upper()
    axis_no = _AXIS_INDEX.get(axis_name, 0)
    axis_name = "XYZ"[axis_no]
    start_radians = math.radians(
        coerce_float(implementation.get("startAngle"), 0.0, unwrap=False)
    )
    rotations = coerce_float(
        implementation.get("numberOfFullRotations"), 0.0, unwrap=False
    )
    direction = -1.0 if bool(implementation.get("reverseDirection", False)) else 1.0
    end_radians = start_radians + math.tau * rotations * direction
    interpolation, easing = _movement_interpolation(implementation)
    return TransformAnimatorSegment(
        axis_name=axis_name,
        axis_no=axis_no,
        start_seconds=start_seconds,
        duration_seconds=duration,
        start_radians=start_radians,
        end_radians=end_radians,
        interpolation=interpolation,
        easing=easing,
        source_type="gameTransformAnimation_RotateOnAxis",
    )


def _compile_move_segment(implementation, start_seconds, duration):
    start_evaluator = _handle_data(implementation.get("startPositionEvaluator"))
    target_evaluator = _handle_data(implementation.get("targetPositionEvaluator"))
    start_type = (
        start_evaluator.get("$type") if isinstance(start_evaluator, dict) else ""
    )
    target_type = (
        target_evaluator.get("$type") if isinstance(target_evaluator, dict) else ""
    )
    if start_type != "gameTransformAnimation_Position_InitialPosition":
        return None, f"gameTransformAnimation_Move[start={start_type or 'unresolved'}]"
    if target_type != "gameTransformAnimation_Position_LocalPosition":
        return (
            None,
            f"gameTransformAnimation_Move[target={target_type or 'unresolved'}]",
        )
    if bool(start_evaluator.get("offsetInWorldSpace", False)):
        return None, "gameTransformAnimation_Move[world-space-initial-offset]"

    interpolation, easing = _movement_interpolation(implementation)
    return (
        TransformAnimatorMoveSegment(
            start_seconds=start_seconds,
            duration_seconds=duration,
            start_offset=vector3_from_data(start_evaluator.get("offset")),
            target_local_position=vector3_from_data(target_evaluator.get("position")),
            interpolation=interpolation,
            easing=easing,
            source_type="gameTransformAnimation_Move",
        ),
        "",
    )


def _compile_animation(animation, anim_impl_lookup):
    if (
        not isinstance(animation, dict)
        or animation.get("$type") != "gameTransformAnimationDefinition"
    ):
        return None
    timeline = animation.get("timeline")
    items = timeline.get("items") if isinstance(timeline, dict) else ()
    if not items:
        return None

    time_scale = _positive_time_scale(animation.get("timeScale", 1.0))
    rotations = []
    moves = []
    unsupported = []
    duration_seconds = 0.0
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_start = max(0.0, coerce_float(item.get("startTime"), 0.0, unwrap=False))
        raw_duration = max(0.0, coerce_float(item.get("duration"), 0.0, unwrap=False))
        start_seconds = raw_start / time_scale
        duration = raw_duration / time_scale
        duration_seconds = max(duration_seconds, start_seconds + duration)
        implementation = _track_implementation(item, anim_impl_lookup)
        source_type = (
            implementation.get("$type") if isinstance(implementation, dict) else ""
        )
        if source_type == "gameTransformAnimation_RotateOnAxis":
            rotations.append(
                _compile_rotation_segment(implementation, start_seconds, duration)
            )
            continue
        if source_type == "gameTransformAnimation_Move":
            segment, reason = _compile_move_segment(
                implementation, start_seconds, duration
            )
            if segment is not None:
                moves.append(segment)
            else:
                unsupported.append(reason)
            continue
        unsupported.append(source_type or "unresolved")

    if not rotations and not moves:
        return None
    times_to_play = max(
        1, int(coerce_float(animation.get("timesToPlay"), 1.0, unwrap=False))
    )
    return TransformAnimatorProgram(
        name=cname_value(animation.get("name")) or "TransformAnimation",
        auto_start=bool(animation.get("autoStart", False)),
        looping=bool(animation.get("looping", False)),
        reverse=bool(animation.get("reverse", False)),
        time_scale=time_scale,
        times_to_play=times_to_play,
        duration_seconds=duration_seconds,
        segments=tuple(rotations),
        move_segments=tuple(moves),
        unsupported_items=tuple(unsupported),
    )


def transform_animator_programs(component, anim_impl_lookup):
    """Compile all named transform-producing programs authored on one animator"""
    if (
        not isinstance(component, dict)
        or component.get("$type") != "gameTransformAnimatorComponent"
    ):
        return ()
    programs = []
    for animation in component.get("animations") or ():
        program = _compile_animation(animation, anim_impl_lookup)
        if program is not None:
            programs.append(program)
    return tuple(programs)


def preview_transform_animator_program(programs):
    programs = tuple(programs or ())
    if not programs:
        return None
    return next((program for program in programs if program.auto_start), programs[0])


def build_transform_animator_lookup(components, anim_impl_lookup):
    lookup = {}
    for component in components or ():
        programs = transform_animator_programs(component, anim_impl_lookup)
        name = component_name(component)
        if name and programs:
            lookup[name] = programs
    return lookup


def _compile_scalar_channels(program, channel_segments):
    duration = max(0.0, float(program.duration_seconds))
    repeats = 1 if program.looping else max(1, int(program.times_to_play))
    channels = {axis: [] for axis in channel_segments}

    def effective(segment):
        (
            start_seconds,
            duration_seconds,
            start_value,
            end_value,
            interpolation,
            easing,
        ) = segment
        if not program.reverse:
            return (
                start_seconds,
                start_seconds + duration_seconds,
                start_value,
                end_value,
                interpolation,
                easing,
            )
        start = max(0.0, duration - (start_seconds + duration_seconds))
        end = max(start, duration - start_seconds)
        return start, end, end_value, start_value, interpolation, easing

    for repeat in range(repeats):
        offset = repeat * duration
        for axis, raw_segments in channel_segments.items():
            segments = sorted(raw_segments, key=lambda segment: effective(segment)[0])
            if not segments:
                continue
            output = channels[axis]
            for segment in segments:
                start, end, start_value, end_value, interpolation, easing = effective(
                    segment
                )
                start += offset
                end += offset
                if not output:
                    if start > offset + _EPSILON:
                        output.append(
                            TransformAnimatorKey(offset, start_value, "CONSTANT")
                        )
                elif start > output[-1].seconds + _EPSILON:
                    previous = output[-1]
                    if previous.interpolation != "CONSTANT":
                        output[-1] = TransformAnimatorKey(
                            previous.seconds,
                            previous.value,
                            "CONSTANT",
                            previous.easing,
                        )
                if output and abs(output[-1].seconds - start) <= _EPSILON:
                    output[-1] = TransformAnimatorKey(
                        start, start_value, interpolation, easing
                    )
                else:
                    output.append(
                        TransformAnimatorKey(start, start_value, interpolation, easing)
                    )
                if end <= start + _EPSILON:
                    output[-1] = TransformAnimatorKey(start, end_value, "CONSTANT")
                else:
                    output.append(TransformAnimatorKey(end, end_value, "CONSTANT"))
            cycle_end = offset + duration
            if output and cycle_end > output[-1].seconds + _EPSILON:
                output.append(
                    TransformAnimatorKey(cycle_end, output[-1].value, "CONSTANT")
                )

    return {axis: tuple(keys) for axis, keys in channels.items() if keys}


def transform_animator_rotation_channel_keys(program):
    """Compile gameTransformAnimation_RotateOnAxis segments into per-axis key streams in timeline seconds"""
    if program is None:
        return {}
    channel_segments = {axis: [] for axis in program.axis_numbers}
    for segment in program.segments:
        channel_segments[segment.axis_no].append(
            (
                segment.start_seconds,
                segment.duration_seconds,
                segment.start_radians,
                segment.end_radians,
                segment.interpolation,
                segment.easing,
            )
        )
    return _compile_scalar_channels(program, channel_segments)


def transform_animator_translation_channel_keys(
    program, base_local_position=(0.0, 0.0, 0.0)
):
    """Compile supported Move segments as local delta-location channels"""
    if program is None or not program.move_segments:
        return {}
    base = tuple(float(value) for value in base_local_position)
    channel_segments = {0: [], 1: [], 2: []}
    for segment in program.move_segments:
        for axis in range(3):
            channel_segments[axis].append(
                (
                    segment.start_seconds,
                    segment.duration_seconds,
                    segment.start_offset[axis],
                    segment.target_local_position[axis] - base[axis],
                    segment.interpolation,
                    segment.easing,
                )
            )
    return _compile_scalar_channels(program, channel_segments)
