from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import bpy

from ...core.log import debug_exception, get_logger
from ...ink.domain.animation import (
    InkAnimationLibrary,
    evaluate_sequence,
    load_animation,
    preferred_sequence,
    switched_on_overrides,
)
from ...ink.domain.writeback import edits_from_json
from ...ink.services.export import edited_document
from ...ink.services.library import LoadedLibrary, load_library
from ...ink.services.scene import render_library
from ..identity import rna_identity
from ..naming import fit_id_name
from ..transactions import track_created_datablock
from .images import PartPixels, pack_texture, render_texture, update_texture
from .materials import rebind_copies
from .text import BlenderFonts

_LOG = get_logger(__name__)
# Widget edits not yet exported, as JSON on the screen's object.
PENDING_EDITS_KEY = "inkPendingEdits"
_FONTS = BlenderFonts()
_PIXELS = PartPixels()
_SCREENS: dict[str, Screen] = {}
# The playing screens' objects by pointer, each with the name it was last found by, so a renamed screen keeps playing.
_PLAYING: dict[int, str] = {}


@dataclass(slots=True)
class Screen:
    object_name: str
    image_name: str
    loaded: LoadedLibrary
    animation: InkAnimationLibrary | None
    max_dimension: int
    base: dict = field(default_factory=dict)
    last_time: float | None = None

    def object(self):
        return bpy.data.objects.get(self.object_name)

    def image(self):
        return bpy.data.images.get(self.image_name)

    def draw(self, overrides: dict) -> bool:
        image = self.image()
        if image is None:
            return False
        canvas, _scale, _laid_out = render_library(
            self.loaded,
            _FONTS,
            _PIXELS,
            overrides=overrides,
            max_dimension=self.max_dimension,
        )
        update_texture(image, canvas)
        return True


def render(
    loaded: LoadedLibrary,
    animation: InkAnimationLibrary | None,
    *,
    max_dimension: int = 2048,
):
    """The switched-on canvas of a loaded library"""
    canvas, _scale, _laid_out = render_library(
        loaded,
        _FONTS,
        _PIXELS,
        overrides=switched_on_overrides(animation),
        max_dimension=max_dimension,
    )
    return canvas


def create_texture(name: str, canvas):
    return render_texture(fit_id_name(name, "_UIRenderTexture"), canvas)


def _stamp(obj, screen: Screen) -> None:
    animation = screen.animation
    obj["cp77_ink_widget_json"] = screen.loaded.path
    obj["cp77_ink_widget_item"] = screen.loaded.item.name
    obj["cp77_ink_atlas_slot"] = int(screen.loaded.preferred_slot)
    obj["cp77_ink_render_texture"] = screen.image_name
    obj["cp77_ink_max_raster_dimension"] = int(screen.max_dimension)
    obj["cp77_ink_animation_json"] = (
        animation.source_path if animation is not None else ""
    )
    obj["cp77_ink_animation_durations"] = json.dumps(
        {
            sequence.name: sequence.duration
            for sequence in (animation.sequences if animation else ())
        },
        separators=(",", ":"),
    )
    preferred = preferred_sequence(animation)
    obj["cp77_ink_active_sequence"] = preferred.name if preferred is not None else ""
    obj["cp77_ink_animation_enabled"] = 0


def register(
    obj,
    image,
    loaded: LoadedLibrary,
    animation: InkAnimationLibrary | None,
    *,
    max_dimension: int = 2048,
) -> Screen:
    """Make obj the screen showing loaded in image"""
    screen = Screen(
        obj.name,
        image.name,
        loaded,
        animation,
        max(1, int(max_dimension)),
        switched_on_overrides(animation),
    )
    _SCREENS[obj.name] = screen
    _PLAYING.pop(rna_identity(obj), None)
    _stamp(obj, screen)
    return screen


def screen_for(obj) -> Screen | None:
    """The screen obj shows, rebuilt from the files its properties name when needed"""
    screen = _SCREENS.get(obj.name)
    if screen is not None:
        return screen
    widget_path = str(obj.get("cp77_ink_widget_json", "") or "")
    if (
        not widget_path
        or not os.path.isfile(widget_path)
        or not obj.get("cp77_ink_render_texture")
    ):
        return None
    item = str(obj.get("cp77_ink_widget_item", "") or "") or None
    edits = edits_from_json(str(obj.get(PENDING_EDITS_KEY, "") or ""))
    document = edited_document(widget_path, item, edits)[0] if edits and item else None
    loaded = load_library(
        widget_path,
        item=item,
        preferred_slot=int(obj.get("cp77_ink_atlas_slot", 0)),
        document=document,
    )
    animation_path = str(obj.get("cp77_ink_animation_json", "") or "")
    animation = (
        load_animation(animation_path)
        if animation_path and os.path.isfile(animation_path)
        else None
    )
    screen = Screen(
        obj.name,
        str(obj["cp77_ink_render_texture"]),
        loaded,
        animation,
        max(1, int(obj.get("cp77_ink_max_raster_dimension", 2048))),
        switched_on_overrides(animation),
    )
    _SCREENS[obj.name] = screen
    return screen


def _seconds(obj, scene) -> float:
    fps = float(scene.render.fps) / max(1.0e-8, float(scene.render.fps_base))
    start = float(obj.get("cp77_ink_animation_start_frame", scene.frame_current))
    return max(0.0, (float(scene.frame_current) - start) / fps)


def _overrides(screen: Screen, sequence, seconds: float) -> dict:
    merged = {path: dict(values) for path, values in screen.base.items()}
    for path, values in evaluate_sequence(sequence, seconds).items():
        merged.setdefault(path, {}).update(values)
    return merged


def play(obj, sequence_name: str, scene) -> bool:
    """Start sequence_name on the screen obj at the current frame"""
    screen = screen_for(obj)
    sequence = (
        screen.animation.sequence(sequence_name)
        if screen is not None and screen.animation
        else None
    )
    if sequence is None:
        return False
    obj["cp77_ink_active_sequence"] = sequence.name
    obj["cp77_ink_animation_start_frame"] = float(scene.frame_current)
    obj["cp77_ink_animation_enabled"] = 1
    screen.last_time = None
    _PLAYING[rna_identity(obj)] = obj.name
    return update(obj, scene)


def stop(obj) -> bool:
    """Stop the screen's sequence and show it switched on again"""
    _PLAYING.pop(rna_identity(obj), None)
    obj["cp77_ink_animation_enabled"] = 0
    screen = screen_for(obj)
    return screen is not None and screen.draw(screen.base)


def update(obj, scene) -> bool:
    screen = screen_for(obj)
    if screen is None or not obj.get("cp77_ink_animation_enabled"):
        return False
    sequence = (
        screen.animation.sequence(str(obj.get("cp77_ink_active_sequence", "")))
        if screen.animation
        else None
    )
    if sequence is None:
        return False
    seconds = _seconds(obj, scene)
    if screen.last_time is not None and abs(seconds - screen.last_time) < 1.0e-6:
        return True
    screen.last_time = seconds
    return screen.draw(_overrides(screen, sequence, seconds))


def clone(source, target, copy_map) -> bool:
    """Give a placement's copy (target of screen source) its own render texture and bound materials"""
    screen = screen_for(source)
    image = screen.image() if screen is not None else None
    if image is None:
        return False
    copy = track_created_datablock("images", image.copy())
    copy.name = fit_id_name(target.name, "_UIRenderTexture")
    try:
        bound = json.loads(str(source.get("cp77_ink_bound_materials", "[]") or "[]"))
    except (TypeError, ValueError):
        bound = []
    names = rebind_copies(
        copy_map, str(source.get("componentName", "") or ""), set(bound), copy
    )
    target["cp77_ink_bound_materials"] = json.dumps(list(names), separators=(",", ":"))
    register(
        target,
        copy,
        screen.loaded,
        screen.animation,
        max_dimension=screen.max_dimension,
    )
    return True


def _playing_object(pointer: int, name: str):
    """The object of a playing screen"""
    obj = bpy.data.objects.get(name)
    if obj is not None and rna_identity(obj) == pointer:
        return obj
    renamed = next(
        (
            candidate
            for candidate in bpy.data.objects
            if rna_identity(candidate) == pointer
        ),
        None,
    )
    return renamed if renamed is not None else obj


def _follow(pointer: int, name: str, obj) -> None:
    """Key a playing screen by the object as it is now, its cached screen with it"""
    del _PLAYING[pointer]
    _PLAYING[rna_identity(obj)] = obj.name
    screen = _SCREENS.pop(name, None) if name != obj.name else None
    if screen is not None:
        screen.object_name = obj.name
        _SCREENS[obj.name] = screen


def frame_changed(scene, _depsgraph=None) -> None:
    for pointer, name in tuple(_PLAYING.items()):
        obj = _playing_object(pointer, name)
        if obj is not None and (rna_identity(obj), obj.name) != (pointer, name):
            _follow(pointer, name, obj)
            pointer = rna_identity(obj)
        try:
            if obj is not None and not obj.users_scene:
                # In no scene it cannot be picked, so nothing could stop it.
                _PLAYING.pop(pointer, None)
                obj["cp77_ink_animation_enabled"] = 0
            elif (
                obj is None
                or not obj.get("cp77_ink_animation_enabled")
                or not update(obj, scene)
            ):
                _PLAYING.pop(pointer, None)
        except Exception:  # a failing screen must not stop the others or the timeline
            debug_exception(_LOG, "The ink screen %s stopped playing", name)
            _PLAYING.pop(pointer, None)
            if obj is not None:
                obj["cp77_ink_animation_enabled"] = 0


def resume_playing() -> None:
    """Play the screens an opened file was saved playing"""
    for obj in bpy.data.objects:
        if (
            obj.get("cp77_ink_animation_enabled")
            and obj.get("cp77_ink_widget_json")
            and obj.users_scene
        ):
            _PLAYING[rna_identity(obj)] = obj.name


def keep_rasters() -> None:
    """Pack the raster each screen last drew, so a saved file shows it when reopened"""
    for screen in _SCREENS.values():
        image = screen.image()
        if image is not None and image.is_dirty:
            pack_texture(image)


def clear() -> None:
    _SCREENS.clear()
    _PLAYING.clear()
