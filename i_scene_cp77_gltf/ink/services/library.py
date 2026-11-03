from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from ...assetio.documents import DocumentLoadError, load_json_payload
from ...assetio.files import png_size
from ...assetio.fonts import font_buffer_bytes
from ...assetio.paths import depot_path_key, strip_json_suffix
from ...assetio.values import cname_text, resource_path_text
from ..domain.text import text_key
from ..model.atlas import AtlasResource, AtlasSlot, part_pixel_rect, read_atlas
from ..model.document import LibraryItem, WidgetLibrary, WidgetRecord, read_library
from ..model.style import StyleSheet, bound_values, read_style
from .resources import Resolver, resolver_for

_SLICE_SAMPLES = 32
# States a screen is shown in when its stylesheet defines none for a widget's own state (vehicle stylesheets have
# only the day/night/... states their script switches between): the active daytime look first.
PREVIEW_STATES = ("day", "inactive")


@dataclass(frozen=True, slots=True)
class PartSource:
    """Where a part's pixels are"""

    kind: str
    path: str
    rect: tuple[int, int, int, int]
    size: tuple[float, float]
    nine_slice: tuple[float, float, float, float] | None


@dataclass(slots=True)
class LoadedAtlas:
    resource: AtlasResource
    slot: AtlasSlot
    slices_folder: str
    texture_path: str
    texture_size: tuple[int, int] | None
    _sources: dict = field(default_factory=dict, repr=False)

    def part_source(self, name: str) -> PartSource | None:
        """The pixels of part name, with its layout size in UltraHD pixels"""
        if name in self._sources:
            return self._sources[name]
        source = None
        uv = self.slot.parts.get(name)
        nine_slice = self.slot.nine_slices.get(name)
        if uv is not None:
            scale = self.slot.native_scale
            path = (
                os.path.join(self.slices_folder, name + ".png")
                if self.slices_folder
                else ""
            )
            size = png_size(path) if path and os.path.isfile(path) else None
            if size is not None:
                source = PartSource(
                    "slice",
                    path,
                    (0, 0, size[0], size[1]),
                    (size[0] * scale, size[1] * scale),
                    nine_slice,
                )
            elif self.texture_path and self.texture_size:
                rect = part_pixel_rect(uv, self.texture_size)
                source = PartSource(
                    "texture",
                    self.texture_path,
                    rect,
                    (rect[2] * scale, rect[3] * scale),
                    nine_slice,
                )
        self._sources[name] = source
        return source


@dataclass(frozen=True, slots=True)
class FontFace:
    family: str
    style: str
    path: str
    data: bytes = b""


@dataclass(slots=True)
class LoadedLibrary:
    path: str
    library: WidgetLibrary
    item: LibraryItem
    atlases: dict[str, LoadedAtlas]
    styles: StyleSheet
    fonts: dict[tuple[str, str], FontFace]
    animation_path: str
    warnings: list[tuple[str, str]]
    preferred_slot: int = 0
    _bound: dict = field(default_factory=dict, repr=False)

    def bound(self, widget: WidgetRecord) -> dict[str, Any]:
        """The values the widget's property bindings take from its style"""
        key = id(widget)
        if key not in self._bound:
            self._bound[key] = bound_values(widget, self.styles)[0]
        return self._bound[key]

    def atlas_for(self, widget: WidgetRecord) -> LoadedAtlas | None:
        depot = widget_atlas_path(widget, self.bound(widget))
        return self.atlases.get(depot_path_key(depot)) if depot else None

    def font(self, family: str, style: str) -> FontFace | None:
        return self.fonts.get((depot_path_key(family), str(style or "").casefold()))


def widget_atlas_path(widget: WidgetRecord, bound: dict[str, Any] | None = None) -> str:
    """The atlas a widget draws from ('' for none, and for widgets that draw a runtime texture)"""
    data = widget.data
    if "textureAtlas" not in data or data.get("useExternalDynamicTexture"):
        return ""
    bound_atlas = (bound or {}).get("textureAtlas")
    return (
        str(bound_atlas)
        if isinstance(bound_atlas, str) and bound_atlas
        else resource_path_text(data.get("textureAtlas"))
    )


def text_font(
    widget: WidgetRecord, bound: dict[str, Any] | None = None
) -> tuple[str, str]:
    """(font family depot path, font style name) a text widget draws with"""
    bound = bound or {}
    family = bound.get("fontFamily")
    family = (
        family
        if isinstance(family, str) and family
        else resource_path_text(widget.data.get("fontFamily"))
    )
    style = bound.get("fontStyle")
    style = (
        style
        if isinstance(style, str) and style
        else cname_text(widget.data.get("fontStyle"))
    )
    return family, style or "Regular"


def _load_json(path: str):
    try:
        return load_json_payload(path)
    except (DocumentLoadError, OSError, ValueError):
        return None


def _texture_size_from_slices(slot: AtlasSlot, folder: str) -> tuple[int, int] | None:
    widths, heights = [], []
    for name, (left, top, right, bottom) in slot.parts.items():
        if len(widths) >= _SLICE_SAMPLES:
            break
        path = os.path.join(folder, name + ".png")
        size = (
            png_size(path)
            if right > left and bottom > top and os.path.isfile(path)
            else None
        )
        if size:
            widths.append(size[0] / (right - left))
            heights.append(size[1] / (bottom - top))
    if not widths:
        return None
    return round(sum(widths) / len(widths)), round(sum(heights) / len(heights))


def _load_atlas(
    depot: str, resolve: Resolver, preferred_slot: int
) -> tuple[LoadedAtlas | None, str]:
    json_path = resolve(depot, ".inkatlas.json")
    document = _load_json(json_path) if json_path else None
    if document is None:
        return None, f"atlas {depot} was not found"
    resource = read_atlas(document, depot)
    for index in dict.fromkeys((preferred_slot, 0, 1, 2)):
        slot = resource.slot(index)
        if slot is None or not slot.parts:
            continue
        folder = (
            os.path.join(strip_json_suffix(json_path), slot.folder)
            if slot.folder
            else ""
        )
        slices = folder if folder and os.path.isdir(folder) else ""
        texture = resolve(slot.texture_path, ".png") if slot.texture_path else ""
        if not (slices or texture):
            continue
        size = png_size(texture) if texture else None
        if size is None and slices:
            size = _texture_size_from_slices(slot, slices)
        return LoadedAtlas(resource, slot, slices, texture, size), ""
    return None, f"atlas {depot} has neither an exported texture nor exported parts"


def _load_styles(paths, resolve: Resolver, warnings: list) -> StyleSheet:
    sheet = StyleSheet(fallback_states=PREVIEW_STATES)
    pending = list(dict.fromkeys(paths))
    while pending:
        depot = pending.pop(0)
        if depot_path_key(depot) in sheet.resources:
            continue
        json_path = resolve(depot, ".inkstyle.json")
        document = _load_json(json_path) if json_path else None
        if document is None:
            warnings.append((depot, f"style {depot} was not found"))
            continue
        resource = read_style(document, depot)
        sheet.add(resource)
        pending.extend(resource.imports)
    return sheet


def _load_fonts(
    requests, resolve: Resolver, warnings: list
) -> dict[tuple[str, str], FontFace]:
    faces: dict[tuple[str, str], FontFace] = {}
    families: dict[str, dict[str, str]] = {}
    for family, style in requests:
        key = depot_path_key(family)
        if key not in families:
            json_path = resolve(family, ".inkfontfamily.json")
            document = _load_json(json_path) if json_path else None
            resource = (
                document.get("Data", {}).get("RootChunk", {})
                if isinstance(document, dict)
                else None
            )
            if resource is None:
                warnings.append((family, f"font family {family} was not found"))
            families[key] = {
                cname_text(entry.get("styleName")).casefold(): resource_path_text(
                    entry.get("font")
                )
                for entry in (resource or {}).get("fontStyles") or ()
                if isinstance(entry, dict)
            }
        font_path = families[key].get(style.casefold(), "")
        face_key = (key, style.casefold())
        if face_key in faces or not families[key]:
            continue
        if not font_path:
            warnings.append((family, f"font family {family} has no {style} style"))
            continue
        ttf = resolve(font_path, ".ttf")
        if ttf:
            faces[face_key] = FontFace(family, style, ttf)
            continue
        exported = resolve(font_path, ".fnt.json")
        data = font_buffer_bytes(_load_json(exported)) if exported else b""
        if data:
            faces[face_key] = FontFace(family, style, "", data)
        else:
            warnings.append((font_path, f"font {font_path} was not found"))
    return faces


def load_library(
    widget_path: str,
    *,
    item: str | None = None,
    resolver: Resolver | None = None,
    preferred_slot: int = 0,
    document: dict | None = None,
) -> LoadedLibrary:
    """Load the widget library at widget_path and what it uses"""
    resolve = resolver or resolver_for(widget_path)
    library = read_library(
        document if document is not None else load_json_payload(widget_path),
        widget_path,
    )
    chosen = library.item(item)
    warnings: list[tuple[str, str]] = []

    styles = _load_styles(
        (widget.style_path for widget in chosen.widgets if widget.style_path),
        resolve,
        warnings,
    )
    bound = {}
    for widget in chosen.widgets:
        values, unresolved = bound_values(widget, styles)
        bound[id(widget)] = values
        for path in unresolved:
            warnings.append((widget.label, f"style path {path} did not resolve"))

    atlases: dict[str, LoadedAtlas] = {}
    missing_atlases: set[str] = set()
    font_requests: list[tuple[str, str]] = []
    keyed_texts = 0
    for widget in chosen.widgets:
        depot = widget_atlas_path(widget, bound[id(widget)])
        key = depot_path_key(depot) if depot else ""
        if key and key not in atlases and key not in missing_atlases:
            atlas, problem = _load_atlas(depot, resolve, preferred_slot)
            if atlas is None:
                missing_atlases.add(key)
                warnings.append((depot, problem))
            else:
                atlases[key] = atlas
        if key in atlases:
            part = cname_text(bound[id(widget)].get("texturePart")) or cname_text(
                widget.data.get("texturePart")
            )
            if part and atlases[key].part_source(part) is None:
                warnings.append(
                    (
                        widget.label,
                        f"part {part} is not in atlas {depot} or was not exported",
                    )
                )
        if widget.type == "inkTextWidget":
            family, style = text_font(widget, bound[id(widget)])
            if family:
                font_requests.append((family, style))
            keyed_texts += bool(text_key(widget.data))
    if keyed_texts:
        warnings.append(
            (
                chosen.name,
                f"{keyed_texts} texts use localization keys and are left blank",
            )
        )

    animation_path = (
        resolve(library.animation_path, ".inkanim.json")
        if library.animation_path
        else ""
    )
    if library.animation_path and not animation_path:
        warnings.append(
            (
                library.animation_path,
                f"animation library {library.animation_path} was not found",
            )
        )

    loaded = LoadedLibrary(
        path=str(widget_path),
        library=library,
        item=chosen,
        atlases=atlases,
        styles=styles,
        fonts=_load_fonts(dict.fromkeys(font_requests), resolve, warnings),
        animation_path=animation_path,
        warnings=warnings,
        preferred_slot=preferred_slot,
    )
    loaded._bound.update(bound)
    return loaded
