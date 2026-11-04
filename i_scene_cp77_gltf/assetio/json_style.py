from __future__ import annotations

import json
import re
from dataclasses import dataclass

# A string (kept as it is) or the exponent marker of a number.
_STRING_OR_EXPONENT = re.compile(r'("(?:[^"\\]|\\.)*")|(?<=[0-9])([eE])(?=[+-]?[0-9])')
# A \u escape (not an escaped backslash followed by "u") and its hex digits.
_UNICODE_ESCAPE = re.compile(r"(?<!\\)((?:\\\\)*)\\u([0-9a-fA-F]{4})")
_LETTERED_ESCAPE = re.compile(r"\\u(?=[0-9a-fA-F]{0,3}[a-fA-F])([0-9a-fA-F]{4})")


@dataclass(frozen=True, slots=True)
class JsonStyle:
    indent: int = 2
    newline: str = "\n"
    trailing_newline: bool = True
    exponent: str = "e"
    ascii_only: bool = False
    upper_hex: bool = True


def json_style(text: str) -> JsonStyle:
    """The style of a JSON text"""
    indent_match = re.search(r"\n( +)\S", text)
    exponent = next(
        (
            match.group(2)
            for match in _STRING_OR_EXPONENT.finditer(text)
            if match.group(2)
        ),
        "e",
    )
    escape = _LETTERED_ESCAPE.search(text)
    return JsonStyle(
        indent=len(indent_match.group(1)) if indent_match else 2,
        newline="\r\n" if "\r\n" in text else "\n",
        trailing_newline=text.endswith("\n"),
        exponent=exponent,
        ascii_only=text.isascii(),
        upper_hex=escape is None or escape.group(1).isupper(),
    )


def styled_dumps(value, style: JsonStyle) -> str:
    text = json.dumps(value, ensure_ascii=style.ascii_only, indent=style.indent)
    if style.ascii_only and style.upper_hex:
        text = _UNICODE_ESCAPE.sub(
            lambda match: match.group(1) + "\\u" + match.group(2).upper(), text
        )
    if style.exponent == "E":
        text = _STRING_OR_EXPONENT.sub(lambda match: match.group(1) or "E", text)
    if style.newline != "\n":
        text = text.replace("\n", style.newline)
    return text + style.newline if style.trailing_newline else text
