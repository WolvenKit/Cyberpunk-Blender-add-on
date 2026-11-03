from __future__ import annotations

import math
import os
from bisect import bisect_right
from dataclasses import dataclass, field
from typing import Any

from ...assetio.documents import load_json_payload
from ...assetio.values import cname_text, coerce_float, strict_handle_data, vector2
from ...bartmoss.scalar import lerp
from ..model.document import color

_SPATIAL_KINDS = frozenset({"scale", "translation", "size", "rotation"})
_TYPE_TO_KIND = {
    "inkanimTransparencyInterpolator": "opacity",
    "inkanimScaleInterpolator": "scale",
    "inkanimTranslationInterpolator": "translation",
    "inkanimSizeInterpolator": "size",
    "inkanimRotationInterpolator": "rotation",
    "inkanimColorInterpolator": "color",
}
_PREFERRED_SEQUENCES = ("loop", "start")


@dataclass(frozen=True, slots=True)
class InkInterpolator:
    kind: str
    start_delay: float
    duration: float
    compiled_start: Any
    compiled_end: Any
    interpolation_key: str = "linear"
    mode_key: str = "easyinout"

    @property
    def end_time(self) -> float:
        return self.start_delay + max(0.0, self.duration)


@dataclass(frozen=True, slots=True)
class InkAnimationChannel:
    kind: str
    interpolators: tuple[InkInterpolator, ...]
    start_times: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class InkAnimationTrack:
    target_path: tuple[int, ...] | None
    channels: tuple[InkAnimationChannel, ...] = ()


@dataclass(frozen=True, slots=True)
class InkAnimationSequence:
    name: str
    tracks: tuple[InkAnimationTrack, ...]
    duration: float
    has_spatial: bool = False

    @property
    def looping(self) -> bool:
        return "loop" in self.name.casefold()


@dataclass(frozen=True, slots=True)
class InkAnimationLibrary:
    source_path: str
    sequences: tuple[InkAnimationSequence, ...]
    unsupported_types: tuple[str, ...] = ()
    sequence_lookup: dict[str, InkAnimationSequence] = field(
        default_factory=dict, repr=False, compare=False
    )

    def sequence(self, name: str) -> InkAnimationSequence | None:
        return self.sequence_lookup.get(str(name or "").casefold())

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sequence.name for sequence in self.sequences)


def _target_path(value: Any) -> tuple[int, ...] | None:
    path = strict_handle_data(value).get("path")
    if not isinstance(path, list):
        return None
    try:
        return tuple(int(index) for index in path)
    except (TypeError, ValueError):
        return None


def _compile_values(kind: str, start: Any, end: Any):
    if kind in {"scale", "translation", "size"}:
        first = vector2(start)
        return first, vector2(end, first)
    if kind == "color":
        first = color(start)
        return first, color(end, first)
    first = coerce_float(start)
    return first, coerce_float(end, first)


def _channels(interpolators: list[InkInterpolator]) -> tuple[InkAnimationChannel, ...]:
    grouped: dict[str, list[InkInterpolator]] = {}
    for interpolator in interpolators:
        grouped.setdefault(interpolator.kind, []).append(interpolator)
    channels = []
    for kind, values in grouped.items():
        values.sort(key=lambda item: item.start_delay)
        channels.append(
            InkAnimationChannel(
                kind, tuple(values), tuple(item.start_delay for item in values)
            )
        )
    return tuple(channels)


def load_animation(path: str) -> InkAnimationLibrary:
    source_path = os.path.abspath(path)
    resource = load_json_payload(source_path).get("Data", {}).get("RootChunk", {})
    if resource.get("$type") != "inkanimAnimationLibraryResource":
        raise ValueError("JSON is not an inkanimAnimationLibraryResource")
    sequences, unsupported = [], set()
    for sequence_handle in resource.get("sequences") or ():
        sequence_data = strict_handle_data(sequence_handle)
        targets = sequence_data.get("targets") or ()
        tracks, duration, spatial = [], 0.0, False
        for index, definition_handle in enumerate(
            sequence_data.get("definitions") or ()
        ):
            interpolators = []
            for interpolator_handle in (
                strict_handle_data(definition_handle).get("interpolators") or ()
            ):
                raw = strict_handle_data(interpolator_handle)
                type_name = str(raw.get("$type") or "<unknown>")
                kind = _TYPE_TO_KIND.get(type_name)
                start_delay = max(0.0, coerce_float(raw.get("startDelay"), 0.0))
                item_duration = max(0.0, coerce_float(raw.get("duration"), 0.0))
                duration = max(duration, start_delay + item_duration)
                if kind is None:
                    unsupported.add(type_name)
                    continue
                if raw.get("isAdditive"):
                    unsupported.add(f"{type_name}:additive")
                    continue
                if raw.get("useRelativeDuration"):
                    unsupported.add(f"{type_name}:relative-duration")
                compiled_start, compiled_end = _compile_values(
                    kind, raw.get("startValue"), raw.get("endValue")
                )
                interpolators.append(
                    InkInterpolator(
                        kind=kind,
                        start_delay=start_delay,
                        duration=item_duration,
                        compiled_start=compiled_start,
                        compiled_end=compiled_end,
                        interpolation_key=str(
                            raw.get("interpolationType") or "Linear"
                        ).casefold(),
                        mode_key=str(
                            raw.get("interpolationMode") or "EasyInOut"
                        ).casefold(),
                    )
                )
                spatial = spatial or kind in _SPATIAL_KINDS
            target = _target_path(targets[index]) if index < len(targets) else None
            tracks.append(InkAnimationTrack(target, _channels(interpolators)))
        sequences.append(
            InkAnimationSequence(
                cname_text(sequence_data.get("name")) or "Sequence",
                tuple(tracks),
                duration,
                spatial,
            )
        )
    sequence_tuple = tuple(sequences)
    return InkAnimationLibrary(
        source_path,
        sequence_tuple,
        tuple(sorted(unsupported)),
        {sequence.name.casefold(): sequence for sequence in sequence_tuple},
    )


def _ease_in(key: str, factor: float) -> float:
    if key in {"sinusoidal", "sine"}:
        return 1.0 - math.cos(factor * math.pi * 0.5)
    if key in {"quadratic", "quad"}:
        return factor * factor
    if key in {"qubic", "cubic"}:
        return factor**3
    if key in {"quartic", "quart"}:
        return factor**4
    if key in {"quintic", "quint"}:
        return factor**5
    if key in {"exponential", "expo"}:
        return 0.0 if factor <= 0.0 else 2.0 ** (10.0 * (factor - 1.0))
    if key in {"circular", "circ"}:
        return 1.0 - math.sqrt(max(0.0, 1.0 - factor * factor))
    if key == "back":
        return 2.70158 * factor**3 - 1.70158 * factor * factor
    if key == "bounce":
        return 1.0 - _bounce_out(1.0 - factor)
    if key == "elastic":
        if factor <= 0.0 or factor >= 1.0:
            return factor
        return -(2.0 ** (10.0 * factor - 10.0)) * math.sin(
            (factor * 10.0 - 10.75) * (2.0 * math.pi / 3.0)
        )
    return factor


def _bounce_out(factor: float) -> float:
    if factor < 1.0 / 2.75:
        return 7.5625 * factor * factor
    if factor < 2.0 / 2.75:
        factor -= 1.5 / 2.75
        return 7.5625 * factor * factor + 0.75
    if factor < 2.5 / 2.75:
        factor -= 2.25 / 2.75
        return 7.5625 * factor * factor + 0.9375
    factor -= 2.625 / 2.75
    return 7.5625 * factor * factor + 0.984375


def easing(interpolation_key: str, mode_key: str, factor: float) -> float:
    factor = max(0.0, min(1.0, float(factor)))
    if mode_key == "easyout":
        return 1.0 - _ease_in(interpolation_key, 1.0 - factor)
    if mode_key == "easyinout":
        if factor < 0.5:
            return 0.5 * _ease_in(interpolation_key, factor * 2.0)
        return 0.5 + 0.5 * (1.0 - _ease_in(interpolation_key, 2.0 - factor * 2.0))
    if mode_key == "easyoutin":
        if factor < 0.5:
            return 0.5 * (1.0 - _ease_in(interpolation_key, 1.0 - factor * 2.0))
        return 0.5 + 0.5 * _ease_in(interpolation_key, factor * 2.0 - 1.0)
    return _ease_in(interpolation_key, factor)


def _value(interpolator: InkInterpolator, time_seconds: float):
    if time_seconds <= interpolator.start_delay or interpolator.duration <= 0.0:
        return interpolator.compiled_start
    if time_seconds >= interpolator.end_time:
        return interpolator.compiled_end
    factor = easing(
        interpolator.interpolation_key,
        interpolator.mode_key,
        (time_seconds - interpolator.start_delay) / interpolator.duration,
    )
    value = lerp(interpolator.compiled_start, interpolator.compiled_end, factor)
    return (
        tuple(float(component) for component in value)
        if isinstance(interpolator.compiled_start, tuple)
        else value
    )


def evaluate_sequence(
    sequence: InkAnimationSequence,
    time_seconds: float,
    result: dict[tuple[int, ...], dict[str, Any]] | None = None,
) -> dict[tuple[int, ...], dict]:
    """Per target path, the values the sequence's channels hold at time_seconds (looping sequences wrap)"""
    if sequence.looping and sequence.duration > 0.0:
        time_seconds = float(time_seconds) % sequence.duration
    else:
        time_seconds = max(0.0, min(float(time_seconds), sequence.duration))
    result = {} if result is None else result
    result.clear()
    for track in sequence.tracks:
        if track.target_path is None or not track.channels:
            continue
        target = result.setdefault(track.target_path, {})
        for channel in track.channels:
            index = max(0, bisect_right(channel.start_times, time_seconds) - 1)
            target[channel.kind] = _value(channel.interpolators[index], time_seconds)
    return result


def preferred_sequence(
    library: InkAnimationLibrary | None,
) -> InkAnimationSequence | None:
    """The sequence a screen is shown with"""
    if library is None or not library.sequences:
        return None
    for name in _PREFERRED_SEQUENCES:
        if (sequence := library.sequence(name)) is not None:
            return sequence
    return library.sequences[0]


def switched_on_overrides(
    library: InkAnimationLibrary | None,
) -> dict[tuple[int, ...], dict[str, Any]]:
    """The overrides of the preferred sequence at its start"""
    sequence = preferred_sequence(library)
    return evaluate_sequence(sequence, 0.0) if sequence is not None else {}
