from __future__ import annotations

import json
import math
import re
from json.decoder import scanstring
from typing import Any

_JSON_NUMBER = re.compile(r"-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?")


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_primitive(text: str, index: int) -> tuple[Any, int]:
    character = text[index]
    if character == '"':
        return scanstring(text, index + 1, True)
    if text.startswith("true", index):
        return True, index + 4
    if text.startswith("false", index):
        return False, index + 5
    if text.startswith("null", index):
        return None, index + 4
    if text.startswith("NaN", index):
        return float("nan"), index + 3
    if text.startswith("Infinity", index):
        return float("inf"), index + 8
    if text.startswith("-Infinity", index):
        return float("-inf"), index + 9
    match = _JSON_NUMBER.match(text, index)
    if match is None:
        raise json.JSONDecodeError("Expecting value", text, index)
    token = match.group(0)
    value = float(token) if any(marker in token for marker in ".eE") else int(token)
    return value, match.end()


def loads(text: str) -> Any:
    """Parse JSON with the C decoder, falling back to the iterative parser for very deep documents"""
    try:
        return json.loads(text)
    except RecursionError:
        return _loads_iterative(text)


def _loads_iterative(text: str) -> Any:
    root = {"kind": "root", "state": "value", "value": None}
    stack = [root]
    index = 0
    length = len(text)

    def attach_value(frame: dict, value: Any) -> None:
        if frame["kind"] == "root":
            frame["value"] = value
            frame["state"] = "done"
        elif frame["kind"] == "array":
            frame["value"].append(value)
            frame["state"] = "comma_or_end"
        else:
            frame["value"][frame["key"]] = value
            frame["key"] = None
            frame["state"] = "comma_or_end"

    def begin_value(frame: dict, value_index: int) -> int:
        character = text[value_index]
        if character == "[":
            value = []
            attach_value(frame, value)
            stack.append({"kind": "array", "state": "value_or_end", "value": value})
            return value_index + 1
        if character == "{":
            value = {}
            attach_value(frame, value)
            stack.append(
                {
                    "kind": "object",
                    "state": "key_or_end",
                    "value": value,
                    "key": None,
                }
            )
            return value_index + 1
        value, next_index = _parse_primitive(text, value_index)
        attach_value(frame, value)
        return next_index

    while stack:
        frame = stack[-1]
        index = _skip_whitespace(text, index)
        kind = frame["kind"]
        state = frame["state"]

        if kind == "root":
            if state == "value":
                if index >= length:
                    raise json.JSONDecodeError("Expecting value", text, index)
                index = begin_value(frame, index)
                continue
            if len(stack) > 1:
                continue
            if index != length:
                raise json.JSONDecodeError("Extra data", text, index)
            return frame["value"]

        if kind == "array":
            if state in {"value_or_end", "value"}:
                if index >= length:
                    raise json.JSONDecodeError("Expecting value", text, index)
                if text[index] == "]":
                    if state == "value":
                        raise json.JSONDecodeError("Expecting value", text, index)
                    stack.pop()
                    index += 1
                    continue
                index = begin_value(frame, index)
                continue
            if index >= length:
                raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
            if text[index] == ",":
                frame["state"] = "value"
                index += 1
                continue
            if text[index] == "]":
                stack.pop()
                index += 1
                continue
            raise json.JSONDecodeError("Expecting ',' delimiter", text, index)

        if state in {"key_or_end", "key"}:
            if index >= length:
                raise json.JSONDecodeError(
                    "Expecting property name enclosed in double quotes", text, index
                )
            if text[index] == "}":
                if state == "key":
                    raise json.JSONDecodeError(
                        "Expecting property name enclosed in double quotes", text, index
                    )
                stack.pop()
                index += 1
                continue
            if text[index] != '"':
                raise json.JSONDecodeError(
                    "Expecting property name enclosed in double quotes", text, index
                )
            frame["key"], index = scanstring(text, index + 1, True)
            frame["state"] = "colon"
            continue
        if state == "colon":
            if index >= length or text[index] != ":":
                raise json.JSONDecodeError("Expecting ':' delimiter", text, index)
            frame["state"] = "value"
            index += 1
            continue
        if state == "value":
            if index >= length:
                raise json.JSONDecodeError("Expecting value", text, index)
            index = begin_value(frame, index)
            continue
        if index >= length:
            raise json.JSONDecodeError("Expecting ',' delimiter", text, index)
        if text[index] == ",":
            frame["state"] = "key"
            index += 1
            continue
        if text[index] == "}":
            stack.pop()
            index += 1
            continue
        raise json.JSONDecodeError("Expecting ',' delimiter", text, index)

    raise json.JSONDecodeError("Expecting value", text, index)


def _key_text(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if value is None:
        return '"null"'
    if value is True:
        return '"true"'
    if value is False:
        return '"false"'
    if isinstance(value, (int, float)):
        return json.dumps(str(value), ensure_ascii=False)
    raise TypeError(
        f"keys must be str, int, float, bool or None, not {type(value).__name__}"
    )


def _non_finite_path(root: Any) -> str | None:
    stack = [(root, "$")]
    while stack:
        value, path = stack.pop()
        if isinstance(value, float) and not math.isfinite(value):
            return path.rstrip()
        if isinstance(value, dict):
            for key, child in value.items():
                stack.append((child, f"{path}.{key}"))
        elif isinstance(value, (list, tuple)):
            for index, child in enumerate(value):
                stack.append((child, f"{path}[{index}]"))
    return None


def dumps(value: Any, *, indent: int | None = 2) -> str:
    """Serialize with the C encoder, or the iterative writer for nesting it cannot handle"""
    if indent is not None:
        indent = max(0, int(indent))
    try:
        if indent is None:
            return json.dumps(
                value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
        return json.dumps(value, ensure_ascii=False, allow_nan=False, indent=indent)
    except RecursionError:
        return _dumps_iterative(value, indent=indent)
    except ValueError as error:
        # Only the float-range error is worth locating; a circular value would never finish the walk.
        if "Out of range float" in str(error):
            non_finite_path = _non_finite_path(value)
            if non_finite_path is not None:
                raise ValueError(
                    f"Non-finite numeric value at {non_finite_path}"
                ) from error
        raise


def _dumps_iterative(value: Any, *, indent: int | None = 2) -> str:
    non_finite_path = _non_finite_path(value)
    if non_finite_path is not None:
        raise ValueError(f"Non-finite numeric value at {non_finite_path}")
    if indent is not None:
        indent = max(0, int(indent))
    parts: list[str] = []
    active: set[int] = set()
    stack: list[tuple[str, Any, int]] = [("value", value, 0)]

    while stack:
        operation, payload, depth = stack.pop()
        if operation == "text":
            parts.append(payload)
            continue
        if operation == "exit":
            active.discard(payload)
            continue
        if not isinstance(payload, (dict, list, tuple)):
            parts.append(json.dumps(payload, ensure_ascii=False, allow_nan=False))
            continue

        identity = id(payload)
        if identity in active:
            raise ValueError("Circular reference detected")
        active.add(identity)
        stack.append(("exit", identity, depth))
        is_object = isinstance(payload, dict)
        items = list(payload.items()) if is_object else list(enumerate(payload))
        parts.append("{" if is_object else "[")
        if not items:
            parts.append("}" if is_object else "]")
            continue

        closing = "}" if is_object else "]"
        if indent is None:
            stack.append(("text", closing, depth))
            for item_index in range(len(items) - 1, -1, -1):
                key, child = items[item_index]
                if item_index < len(items) - 1:
                    stack.append(("text", ",", depth))
                stack.append(("value", child, depth + 1))
                if is_object:
                    stack.append(("text", _key_text(key) + ":", depth + 1))
            continue

        child_indent = " " * (indent * (depth + 1))
        close_indent = " " * (indent * depth)
        stack.append(("text", "\n" + close_indent + closing, depth))
        for item_index in range(len(items) - 1, -1, -1):
            key, child = items[item_index]
            if item_index < len(items) - 1:
                stack.append(("text", ",", depth))
            stack.append(("value", child, depth + 1))
            if is_object:
                stack.append(("text", _key_text(key) + ": ", depth + 1))
            stack.append(("text", "\n" + child_indent, depth + 1))

    return "".join(parts)
