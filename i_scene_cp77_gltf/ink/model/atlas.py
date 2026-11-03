from __future__ import annotations

from dataclasses import dataclass

from ...assetio.values import cname_text, coerce_float, resource_path_text

# Slot index order: UltraHD, FullHD, HD. Layout sizes are in UltraHD pixels, so a slot's part sizes scale by its
# native scale.
RESOLUTION_FOLDERS = ("2160p", "1080p", "720p")
NATIVE_SCALES = (1.0, 2.0, 3.0)


@dataclass(frozen=True, slots=True)
class AtlasSlot:
    index: int
    texture_path: str
    parts: dict[str, tuple[float, float, float, float]]
    nine_slices: dict[str, tuple[float, float, float, float]]

    @property
    def folder(self) -> str:
        return (
            RESOLUTION_FOLDERS[self.index]
            if self.index < len(RESOLUTION_FOLDERS)
            else ""
        )

    @property
    def native_scale(self) -> float:
        return NATIVE_SCALES[self.index] if self.index < len(NATIVE_SCALES) else 1.0


@dataclass(frozen=True, slots=True)
class AtlasResource:
    path: str
    slots: tuple[AtlasSlot, ...]

    def slot(self, index: int) -> AtlasSlot | None:
        return self.slots[index] if 0 <= index < len(self.slots) else None


def _rect(value) -> tuple[float, float, float, float]:
    value = value if isinstance(value, dict) else {}
    return tuple(
        coerce_float(value.get(side), 0.0)
        for side in ("Left", "Top", "Right", "Bottom")
    )


def _named_rects(entries, key: str) -> dict[str, tuple[float, float, float, float]]:
    rects = {}
    for entry in entries or ():
        if isinstance(entry, dict) and (name := cname_text(entry.get("partName"))):
            rects.setdefault(name, _rect(entry.get(key)))
    return rects


def read_atlas(document: dict, path: str = "") -> AtlasResource:
    resource = (
        document.get("Data", {}).get("RootChunk", {})
        if isinstance(document, dict)
        else {}
    )
    slots = resource.get("slots")
    elements = slots.get("Elements") if isinstance(slots, dict) else slots
    return AtlasResource(
        str(path),
        tuple(
            AtlasSlot(
                index=index,
                texture_path=resource_path_text(slot.get("texture")),
                parts=_named_rects(slot.get("parts"), "clippingRectInUVCoords"),
                nine_slices=_named_rects(slot.get("slices"), "nineSliceScaleRect"),
            )
            for index, slot in enumerate(
                element if isinstance(element, dict) else {}
                for element in elements or ()
            )
        ),
    )


def part_pixel_rect(
    uv: tuple[float, float, float, float], texture_size: tuple[int, int]
) -> tuple[int, int, int, int]:
    """(x, y, width, height) of a part's UV rect in a texture of texture_size pixels, top-left origin"""
    width, height = texture_size
    left, top = round(uv[0] * width), round(uv[1] * height)
    right, bottom = round(uv[2] * width), round(uv[3] * height)
    return left, top, max(0, right - left), max(0, bottom - top)
