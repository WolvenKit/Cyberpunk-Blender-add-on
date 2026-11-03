from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Protocol

from ...assetio.values import cname_or_empty, cname_text, coerce_float

DEFAULT_FONT_SIZE = 32.0
_LOCALIZATION_KEY_PREFIXES = (
    "LOCKEY#",
    "COMMON-",
    "GAMEPLAY-",
    "STORY-",
    "UI-",
    "DEBUG-",
    "OBSOLETE-",
)


class Measurer(Protocol):
    def advance(self, font: Any, size: float, text: str) -> float:
        """The advance width of text in pixels, without tracking"""

    def vertical(self, font: Any, size: float) -> tuple[int, int]:
        """(ascent, descent) in whole pixels at size"""


@dataclass(frozen=True, slots=True)
class TextStyle:
    font: Any
    size: float
    tracking: float
    line_height: float
    letter_case: str
    wrap_width: float
    overflow: str
    justification: str
    h_align: str
    v_align: str


@dataclass(frozen=True, slots=True)
class TextLine:
    text: str
    width: float
    x: float
    top: float
    height: float


@dataclass(frozen=True, slots=True)
class TextBlock:
    lines: tuple[TextLine, ...]
    width: float
    height: float
    ascent: float
    size: float


def apply_letter_case(text: str, letter_case: str) -> str:
    if letter_case == "UpperCase":
        return text.upper()
    if letter_case == "LowerCase":
        return text.lower()
    return text


def _localization_value(data: dict) -> str:
    entry = data.get("localizationString") if isinstance(data, dict) else None
    return str(entry.get("value") or "") if isinstance(entry, dict) else ""


def text_key(data: dict) -> str:
    """The localization key whose string a text widget shows, or ''"""
    value = _localization_value(data)
    if value:
        return value if value.upper().startswith(_LOCALIZATION_KEY_PREFIXES) else ""
    return cname_or_empty(data.get("textIdKey")) if isinstance(data, dict) else ""


def text_content(data: dict) -> str:
    """The string a text widget shows outside the game's localization"""
    if text_key(data):
        return ""
    localized = _localization_value(data)
    if localized:
        return localized
    value = data.get("text") if isinstance(data, dict) else None
    if isinstance(value, dict):
        value = value.get("$value", value.get("value", ""))
    return "" if value is None else str(value)


def wrap_width(data: dict, size: tuple[float, float], fit_to_content: bool) -> float:
    """The width a text wraps at, or 0 for no wrapping"""
    info = data.get("wrappingInfo") if isinstance(data, dict) else None
    info = info if isinstance(info, dict) else {}
    width = coerce_float(info.get("wrappingAtPosition"), 0.0)
    if (
        coerce_float(info.get("autoWrappingEnabled"), 0.0)
        and not fit_to_content
        and size[0] >= 1.0
    ):
        width = min(width, float(size[0])) if width >= 1.0 else float(size[0])
    return max(0.0, width)


def _enum(data: dict, key: str, default: str) -> str:
    value = data.get(key)
    return str(cname_text(value) if isinstance(value, dict) else value or default)


def text_style(
    data: dict,
    bound: dict,
    *,
    font: Any,
    size: tuple[float, float],
    fit_to_content: bool,
) -> TextStyle:
    """A text widget's style from its fields, with style-bound font size and letter case taking precedence"""
    font_size = bound.get("fontSize", data.get("fontSize"))
    return TextStyle(
        font=font,
        size=coerce_float(font_size, DEFAULT_FONT_SIZE) or DEFAULT_FONT_SIZE,
        tracking=coerce_float(data.get("tracking"), 0.0),
        line_height=coerce_float(data.get("lineHeightPercentage"), 1.0) or 1.0,
        letter_case=str(
            bound.get("letterCase") or _enum(data, "letterCase", "OriginalCase")
        ),
        wrap_width=wrap_width(data, size, fit_to_content),
        overflow=_enum(data, "textOverflowPolicy", "None"),
        justification=_enum(data, "justification", "Left"),
        h_align=_enum(data, "textHorizontalAlignment", "Left"),
        v_align=_enum(data, "textVerticalAlignment", "Top"),
    )


def _line_width(text: str, style: TextStyle, measurer: Measurer) -> float:
    return measurer.advance(style.font, style.size, text) + style.tracking * len(text)


def _wrapped(paragraph: str, style: TextStyle, measurer: Measurer) -> list[str]:
    if style.wrap_width <= 0.0:
        return [paragraph]
    lines, current = [], ""
    for word in paragraph.split(" "):
        candidate = f"{current} {word}" if current else word
        if not current or _line_width(candidate, style, measurer) <= style.wrap_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def layout_text(text: str, style: TextStyle, measurer: Measurer) -> TextBlock:
    shown = apply_letter_case(str(text or "").replace("\r\n", "\n"), style.letter_case)
    ascent, descent = measurer.vertical(style.font, style.size)
    line_height = (ascent - descent) * style.line_height
    texts = [
        line
        for paragraph in shown.split("\n")
        for line in _wrapped(paragraph, style, measurer)
    ]
    widths = [_line_width(line, style, measurer) for line in texts]
    block_width = max(widths, default=0.0)
    lines = []
    for index, (line, width) in enumerate(zip(texts, widths)):
        if style.justification == "Center":
            x = (block_width - width) / 2.0
        elif style.justification == "Right":
            x = block_width - width
        else:
            x = 0.0
        lines.append(TextLine(line, width, x, index * line_height, line_height))
    return TextBlock(
        tuple(lines),
        block_width,
        line_height * len(lines),
        float(ascent),
        float(style.size),
    )


def fit_block(
    text: str, style: TextStyle, measurer: Measurer, box: tuple[float, float]
) -> TextBlock:
    """The text's block"""
    block = layout_text(text, style, measurer)
    if style.overflow != "AdjustToSize" or box[0] <= 0.0 or box[1] <= 0.0:
        return block
    size = style.size
    while (block.width > box[0] or block.height > box[1]) and size > 1.0:
        size -= 1.0
        block = layout_text(text, replace(style, size=size), measurer)
    return block


def block_origin(
    block: TextBlock, box: tuple[float, float], style: TextStyle
) -> tuple[float, float]:
    """Where the block's top-left sits in the widget's area"""
    width, height = box
    x = (
        (width - block.width) / 2.0
        if style.h_align == "Center"
        else (width - block.width if style.h_align == "Right" else 0.0)
    )
    y = (
        (height - block.height) / 2.0
        if style.v_align == "Center"
        else (height - block.height if style.v_align == "Bottom" else 0.0)
    )
    return x, y
