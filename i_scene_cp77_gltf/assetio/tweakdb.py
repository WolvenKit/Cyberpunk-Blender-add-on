from __future__ import annotations

import copy
import math
import os
import re
from dataclasses import dataclass

from .files import read_bytes
from .paths import depot_path_key, relative_local_path
from .tweakdb_compiled import tweakdb_id


@dataclass(frozen=True, slots=True)
class TaggedValue:
    operation: str
    value: object


@dataclass(frozen=True, slots=True)
class FieldUpdate:
    operation: str
    value: object


@dataclass(frozen=True, slots=True)
class RecordDefinition:
    record_id: str
    base: str
    fields: dict
    source: str
    source_kind: str
    type_name: str = ""


@dataclass(frozen=True, slots=True)
class ResolvedRecord:
    record_id: str
    fields: dict
    sources: tuple[str, ...]
    type_name: str = ""


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    value: str
    line: int


class TweakParseError(ValueError):
    pass


# TweakXL list tags; longer names first so a prefix never shadows them.
LIST_TAGS = (
    "append-once",
    "prepend-once",
    "append-from",
    "prepend-from",
    "remove-all",
    "append",
    "prepend",
    "remove",
    "merge",
)
# Marks an inline mapping read from an override file without $base: it describes a new record, not a change to
# the one the field named before.
FRESH_KEY = "$fresh"
_ATTRIBUTE_KEYS = frozenset(("$base", "$type", FRESH_KEY))


def _list_tag(value):
    """(operation, remainder) when value starts with a TweakXL list tag, else None"""
    if not value.startswith("!"):
        return None
    name, _separator, remainder = value[1:].partition(" ")
    return (name, remainder.strip()) if name in LIST_TAGS else None


def _parse_number(value):
    cleaned = value.rstrip("fF")
    if any(character in cleaned for character in ".eE"):
        result = float(cleaned)
    else:
        result = int(cleaned)
    if isinstance(result, float) and not math.isfinite(result):
        raise ValueError("Numeric values must be finite")
    return result


def _tokenize_tweak(text):
    tokens = []
    index = 0
    line = 1
    length = len(text)
    while index < length:
        character = text[index]
        if character.isspace():
            line += character == "\n"
            index += 1
            continue
        if text.startswith("//", index):
            end = text.find("\n", index + 2)
            index = length if end < 0 else end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end < 0:
                raise TweakParseError(f"Unterminated block comment at line {line}")
            line += text[index : end + 2].count("\n")
            index = end + 2
            continue
        if character in "\"'":
            quote = character
            start_line = line
            index += 1
            value = []
            while index < length:
                character = text[index]
                if character == quote:
                    index += 1
                    break
                if (
                    character == "\\"
                    and index + 1 < length
                    and text[index + 1] == quote
                ):
                    value.append(quote)
                    index += 2
                    continue
                value.append(character)
                line += character == "\n"
                index += 1
            else:
                raise TweakParseError(f"Unterminated string at line {start_line}")
            tokens.append(_Token("STRING", "".join(value), start_line))
            continue
        if text.startswith("+=", index):
            tokens.append(_Token("SYMBOL", "+=", line))
            index += 2
            continue
        if character in "{}[]():;=,<>":
            tokens.append(_Token("SYMBOL", character, line))
            index += 1
            continue
        if (
            character in "+-"
            and index + 1 < length
            and (text[index + 1].isdigit() or text[index + 1] == ".")
        ):
            start = index
            index += 1
            while index < length and text[index] in "0123456789.eEfF+-":
                if text[index] in "+-" and text[index - 1] not in "eE":
                    break
                index += 1
            tokens.append(_Token("NUMBER", text[start:index], line))
            continue
        if character.isdigit() or (
            character == "." and index + 1 < length and text[index + 1].isdigit()
        ):
            start = index
            index += 1
            while index < length and text[index] in "0123456789.eEfF+-":
                if text[index] in "+-" and text[index - 1] not in "eE":
                    break
                index += 1
            tokens.append(_Token("NUMBER", text[start:index], line))
            continue
        start = index
        while (
            index < length
            and not text[index].isspace()
            and text[index] not in "{}[]():;=,<>\"'"
        ):
            if (
                text.startswith("//", index)
                or text.startswith("/*", index)
                or text.startswith("+=", index)
            ):
                break
            index += 1
        if start == index:
            raise TweakParseError(f"Unexpected character {character!r} at line {line}")
        tokens.append(_Token("IDENT", text[start:index], line))
    return tokens


class _TweakParser:
    def __init__(self, text, source):
        self.tokens = _tokenize_tweak(text)
        self.index = 0
        self.source = source
        self.package = ""

    def parse(self):
        definitions = []
        while not self._at_end():
            token = self._peek()
            if token.value == "package":
                package_line = self._take().line
                if not self._at_end() and self._peek().line == package_line:
                    self.package = self._take().value
                self._skip_line(package_line)
                continue
            if token.value == "using":
                self._skip_line(self._take().line)
                continue
            if token.kind not in {"IDENT", "STRING"}:
                self._take()
                continue
            name = self._take().value
            base = ""
            if self._accept(":"):
                base = self._take().value
            if not self._accept("{"):
                self._skip_to_top_level()
                continue
            fields = self._parse_body()
            self._accept(";")
            record_id = self._qualify(name)
            definitions.append(
                RecordDefinition(
                    record_id,
                    self._qualify(base) if base else "",
                    fields,
                    self.source,
                    "tweak",
                )
            )
        return definitions

    def _parse_body(self):
        fields = {}
        while not self._at_end() and self._peek().value != "}":
            prefix = []
            while not self._at_end() and self._peek().value not in {
                "=",
                "+=",
                "}",
                ";",
            }:
                prefix.append(self._take())
            if self._accept(";"):
                continue
            if self._peek().value == "}":
                break
            if self._at_end() or self._peek().value not in {"=", "+="}:
                self._take()
                continue
            operation = self._take().value
            field_tokens = [
                token for token in prefix if token.kind in {"IDENT", "STRING"}
            ]
            if not field_tokens:
                raise TweakParseError(f"Missing field name in {self.source}")
            field_name = field_tokens[-1].value
            value = self._parse_value()
            fields[field_name] = (
                FieldUpdate("append", value) if operation == "+=" else value
            )
            self._accept(";")
            self._accept(",")
        self._expect("}")
        return fields

    def _parse_value(self):
        token = self._peek()
        if token.value == "[":
            self._take()
            values = []
            while not self._at_end() and self._peek().value != "]":
                values.append(self._parse_value())
                self._accept(",")
            self._expect("]")
            return values
        if token.value == "(":
            self._take()
            values = []
            while not self._at_end() and self._peek().value != ")":
                values.append(self._parse_value())
                self._accept(",")
            self._expect(")")
            return tuple(values)
        if token.value == "{":
            self._take()
            value = self._parse_body()
            if self._accept(":"):
                type_name = self._take().value
                value["$type"] = type_name
                value["$base"] = self._qualify(type_name)
            return value
        token = self._take()
        if token.kind == "NUMBER":
            try:
                return _parse_number(token.value)
            except ValueError as error:
                raise TweakParseError(
                    f"Invalid number {token.value!r} at line {token.line} in {self.source}: {error}"
                ) from error
        if token.kind == "STRING":
            return token.value
        lowered = token.value.casefold()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in {"null", "none"}:
            return None
        return token.value

    def _qualify(self, value):
        value = str(value or "")
        if not value or "." in value or not self.package:
            return value
        return f"{self.package}.{value}"

    def _skip_line(self, line):
        while not self._at_end() and self._peek().line == line:
            self._take()

    def _skip_to_top_level(self):
        start_line = self._peek().line if not self._at_end() else -1
        while not self._at_end() and self._peek().line == start_line:
            self._take()

    def _peek(self):
        if self._at_end():
            self._unexpected_end()
        return self.tokens[self.index]

    def _take(self):
        token = self._peek()
        self.index += 1
        return token

    def _unexpected_end(self):
        line = self.tokens[-1].line if self.tokens else 1
        raise TweakParseError(
            f"Unexpected end of input after line {line} in {self.source}"
        )

    def _accept(self, value):
        if not self._at_end() and self._peek().value == value:
            self.index += 1
            return True
        return False

    def _expect(self, value):
        if not self._accept(value):
            line = self._peek().line if not self._at_end() else "EOF"
            raise TweakParseError(f"Expected {value!r} at line {line} in {self.source}")

    def _at_end(self):
        return self.index >= len(self.tokens)


def parse_tweak_text(text, source="<memory>"):
    return _TweakParser(text, source).parse()


def _strip_yaml_comment(value):
    quote = ""
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in "\"'":
            if quote == character:
                quote = ""
            elif not quote:
                quote = character
            continue
        if character == "#" and not quote:
            return value[:index].rstrip()
    return value.rstrip()


def _split_yaml_key(value):
    quote = ""
    depth = 0
    escaped = False
    for index, character in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote == '"' and character == "\\":
            escaped = True
            continue
        if character in "\"'":
            if quote == character:
                quote = ""
            elif not quote:
                quote = character
            continue
        if quote:
            continue
        if character in "[{(":
            depth += 1
        elif character in "]})":
            depth -= 1
        elif character == ":" and depth == 0:
            return value[:index].strip(), value[index + 1 :].strip()
    raise TweakParseError(f"Expected YAML mapping entry: {value}")


class _InlineYamlParser:
    def __init__(self, text):
        self.text = text
        self.index = 0

    def parse(self):
        value = self._value()
        self._space()
        if self.index != len(self.text):
            raise TweakParseError(
                f"Unexpected YAML scalar content: {self.text[self.index :]}"
            )
        return value

    def _value(self):
        self._space()
        if self._accept("{"):
            result = {}
            self._space()
            while not self._accept("}"):
                key = self._token(":")
                self._expect(":")
                result[str(key)] = self._value()
                self._space()
                if self._accept("}"):
                    break
                self._expect(",")
            return result
        if self._accept("["):
            result = []
            self._space()
            while not self._accept("]"):
                result.append(self._value())
                self._space()
                if self._accept("]"):
                    break
                self._expect(",")
            return result
        if self._peek() in "\"'":
            return self._quoted()
        token = self._token(",]}").strip()
        tag = _list_tag(token)
        if tag is not None:
            operation, remainder = tag
            return TaggedValue(
                operation, _parse_yaml_scalar(remainder) if remainder else None
            )
        return _parse_plain_scalar(token)

    def _quoted(self):
        quote = self._peek()
        self.index += 1
        result = []
        while self.index < len(self.text):
            character = self.text[self.index]
            self.index += 1
            if character == quote:
                if quote == "'" and self._peek() == "'":
                    result.append("'")
                    self.index += 1
                    continue
                return "".join(result)
            if quote == '"' and character == "\\" and self.index < len(self.text):
                escaped = self.text[self.index]
                self.index += 1
                result.append({"n": "\n", "r": "\r", "t": "\t"}.get(escaped, escaped))
            else:
                result.append(character)
        raise TweakParseError("Unterminated YAML string")

    def _token(self, terminators):
        self._space()
        start = self.index
        quote = ""
        depth = 0
        while self.index < len(self.text):
            character = self.text[self.index]
            if character in "\"'":
                if quote == character:
                    quote = ""
                elif not quote:
                    quote = character
            elif not quote:
                if character in "[{(":
                    depth += 1
                elif character in "]})" and depth:
                    depth -= 1
                elif character in terminators and depth == 0:
                    break
            self.index += 1
        return self.text[start : self.index].strip()

    def _space(self):
        while self.index < len(self.text) and self.text[self.index].isspace():
            self.index += 1

    def _peek(self):
        return self.text[self.index] if self.index < len(self.text) else ""

    def _accept(self, value):
        self._space()
        if self.text.startswith(value, self.index):
            self.index += len(value)
            return True
        return False

    def _expect(self, value):
        if not self._accept(value):
            raise TweakParseError(f"Expected {value!r} in {self.text!r}")


def _parse_plain_scalar(value):
    lowered = value.casefold()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none", "~"}:
        return None
    if not value:
        return ""
    try:
        return _parse_number(value)
    except ValueError:
        return value


def _parse_yaml_scalar(value):
    value = value.strip()
    tag = _list_tag(value)
    if tag is not None:
        operation, remainder = tag
        return TaggedValue(
            operation, _parse_yaml_scalar(remainder) if remainder else None
        )
    if value.startswith(("{", "[", '"', "'")):
        return _InlineYamlParser(value).parse()
    return _parse_plain_scalar(value)


_BLOCK_SCALAR_HEADER = re.compile(r"^([|>])([1-9]?)([+-]?)([1-9]?)$")
_ANCHOR = re.compile(r"^&([^\s\[\]{},]+)\s*(.*)$")


def _split_anchor(value):
    """(anchor name or "", the rest) for a value that may start with &name"""
    match = _ANCHOR.match(value)
    return (match.group(1), match.group(2).strip()) if match else ("", value)


def _line_value(content):
    """The value text of a mapping entry or list item line, or "" when the line opens a block"""
    value = content
    if value.startswith("-") and (len(value) == 1 or value[1] == " "):
        value = value[1:].strip()
    if ":" in value and not value.startswith(("{", "[", '"', "'", "*", "&")):
        try:
            _key, value = _split_yaml_key(value)
        except TweakParseError:
            pass
    return _split_anchor(value)[1]


def _fold_block_lines(lines):
    """YAML folding of block scalar lines"""
    text = ""
    for index, line in enumerate(lines):
        if index == 0:
            text = line
            continue
        previous = lines[index - 1]
        previous_indented = previous.startswith((" ", "\t"))
        indented = line.startswith((" ", "\t"))
        if previous and line and not previous_indented and not indented:
            text += " " + line
        elif previous and not line and not previous_indented:
            continue
        else:
            text += "\n" + line
    return text


def _read_block_scalar(raw_lines, index, parent_indent, header):
    """The block scalar (| or >) whose header ends the line before index, and the index after it"""
    style, first_digit, chomping, second_digit = header.groups()
    explicit = int(first_digit or second_digit or 0)
    block_indent = parent_indent + explicit if explicit else None
    collected = []
    while index < len(raw_lines):
        expanded = raw_lines[index].expandtabs(2)
        if expanded.strip():
            indent = len(expanded) - len(expanded.lstrip())
            if indent <= parent_indent or (
                block_indent is not None and indent < block_indent
            ):
                break
            if block_indent is None:
                block_indent = indent
            collected.append(expanded[block_indent:])
        else:
            collected.append("")
        index += 1
    trailing = 0
    while collected and not collected[-1]:
        collected.pop()
        trailing += 1
    body = "\n".join(collected) if style == "|" else _fold_block_lines(collected)
    if chomping == "-":
        return body, index
    if chomping == "+":
        return body + "\n" * (trailing + (1 if collected else 0)), index
    return (body + "\n" if collected else ""), index


def parse_yaml_text(text, source="<memory>", diagnostics=None):
    """A TweakXL YAML document"""
    raw_lines = text.splitlines()
    lines = []
    block_scalars = {}
    raw_index = 0
    while raw_index < len(raw_lines):
        raw_line = raw_lines[raw_index]
        line_number = raw_index + 1
        raw_index += 1
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        expanded = raw_line.expandtabs(2)
        content = _strip_yaml_comment(expanded.lstrip())
        if not content:
            continue
        indent = len(expanded) - len(expanded.lstrip())
        header = _BLOCK_SCALAR_HEADER.match(_line_value(content))
        if header is not None:
            block_scalars[line_number], raw_index = _read_block_scalar(
                raw_lines, raw_index, indent, header
            )
        lines.append((indent, content, line_number))
    if not lines:
        return {}

    anchors = {}

    def alias(text, line_number):
        name = text[1:].strip()
        if name not in anchors:
            raise TweakParseError(
                f"Unknown YAML alias *{name} at line {line_number} in {source}"
            )
        return copy.deepcopy(anchors[name])

    def scalar(value_text, line_number):
        """The value a line gives inline"""
        anchor, value_text = _split_anchor(value_text)
        items = (
            [item.strip() for item in value_text[1:-1].split(",")]
            if value_text[:1] == "[" and value_text[-1:] == "]"
            else ()
        )
        if value_text.startswith("*"):
            value = alias(value_text, line_number)
        elif items and all(item.startswith("*") for item in items):
            value = [alias(item, line_number) for item in items]
        elif line_number in block_scalars and _BLOCK_SCALAR_HEADER.match(value_text):
            value = block_scalars[line_number]
        elif value_text:
            value = _parse_yaml_scalar(value_text)
        else:
            value = None
        if anchor:
            anchors[anchor] = value
        return value

    def merge_sources(value, line_number):
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return list(value)
        raise TweakParseError(
            f"A YAML merge key needs a mapping or a list of mappings at line {line_number} in {source}"
        )

    def child_block(index, anchor):
        child, index = parse_block(index, lines[index][0])
        if anchor:
            anchors[anchor] = child
        return child, index

    def parse_block(index, indent):
        is_list = lines[index][1].startswith("-")
        result = [] if is_list else {}
        merged = []
        while index < len(lines):
            current_indent, content, line_number = lines[index]
            if current_indent < indent:
                break
            if current_indent > indent:
                raise TweakParseError(
                    f"Unexpected indentation at line {line_number} in {source}"
                )
            if is_list:
                if not content.startswith("-"):
                    break
                remainder = content[1:].strip()
                tag = _list_tag(remainder)
                if (
                    tag is not None
                    and not tag[1]
                    and index + 1 < len(lines)
                    and lines[index + 1][0] > indent
                ):
                    # A tag alone on its item applies to the block below it, such as an appended inline record.
                    child, index = parse_block(index + 1, lines[index + 1][0])
                    result.append(TaggedValue(tag[0], child))
                    continue
                anchor, bare = _split_anchor(remainder)
                if not bare:
                    if index + 1 >= len(lines) or lines[index + 1][0] <= indent:
                        result.append(scalar(remainder, line_number))
                        index += 1
                    else:
                        child, index = child_block(index + 1, anchor)
                        result.append(child)
                    continue
                if ":" in bare and not bare.startswith(("!", "{", "[", '"', "'", "*")):
                    key, value_text = _split_yaml_key(bare)
                    item = {
                        str(_parse_yaml_scalar(key)): scalar(value_text, line_number)
                        if value_text
                        else None
                    }
                    index += 1
                    if index < len(lines) and lines[index][0] > indent:
                        child, index = parse_block(index, lines[index][0])
                        if isinstance(child, dict):
                            item.update(child)
                    if anchor:
                        anchors[anchor] = item
                    result.append(item)
                    continue
                result.append(scalar(remainder, line_number))
                index += 1
                continue

            if content.startswith("-"):
                break
            key, value_text = _split_yaml_key(content)
            parsed_key = str(_parse_yaml_scalar(key))
            anchor, bare = _split_anchor(value_text)
            if bare or index + 1 >= len(lines) or lines[index + 1][0] <= indent:
                value = scalar(value_text, line_number) if value_text else None
                index += 1
            else:
                value, index = child_block(index + 1, anchor)
            if parsed_key == "<<":
                merged.extend(merge_sources(value, line_number))
                continue
            if parsed_key in result and diagnostics is not None:
                diagnostics.append(
                    f"Duplicate key {parsed_key!r} at line {line_number} in {source}; the last value is used"
                )
            result[parsed_key] = value
        # Merged mappings never override keys the mapping itself gives, and earlier sources win over later ones.
        for source_mapping in merged:
            for key, value in source_mapping.items():
                result.setdefault(key, copy.deepcopy(value))
        return result, index

    document, final_index = parse_block(0, lines[0][0])
    if final_index != len(lines):
        line_number = lines[final_index][2]
        raise TweakParseError(f"Could not parse YAML line {line_number} in {source}")
    return document


class TweakDatabase:
    """Records from .tweak and TweakXL YAML sources, resolved through inheritance and later changes"""

    def __init__(self):
        self._definitions = {}
        self._pending_fields = []
        self._provisional_inline = {}
        self._cache = {}
        self.diagnostics = []

    def copy(self):
        """An independent database with the same definitions, for layering overrides on a shared base"""
        other = TweakDatabase()
        other._definitions = {
            record_id: list(definitions)
            for record_id, definitions in self._definitions.items()
        }
        other._pending_fields = list(self._pending_fields)
        other._provisional_inline = {
            record_id: list(names)
            for record_id, names in self._provisional_inline.items()
        }
        other.diagnostics = list(self.diagnostics)
        return other

    def add_tweak_text(self, text, source="<memory>", *, override=False):
        for definition in parse_tweak_text(text, source):
            if override:
                definition = RecordDefinition(
                    definition.record_id,
                    definition.base,
                    _mark_fresh_fields(definition.fields),
                    definition.source,
                    "tweak-override",
                    definition.type_name,
                )
            self._add_definition(definition)

    def add_yaml_text(self, text, source="<memory>", *, override=False):
        document = parse_yaml_text(text, source, self.diagnostics)
        if not isinstance(document, dict):
            raise TweakParseError(f"YAML root must be a mapping in {source}")
        kind = "yaml-override" if override else "yaml"
        for key, value in document.items():
            key = str(key)
            if key.startswith("$"):
                continue
            if isinstance(value, dict) and (
                "$base" in value
                or "$type" in value
                or (override and key in self._definitions)
            ):
                base = value.get("$base")
                type_name = str(value.get("$type", "") or "")
                fields = {
                    name: child
                    for name, child in value.items()
                    if name not in _ATTRIBUTE_KEYS
                }
                if override:
                    fields = _mark_fresh_fields(fields)
                self._add_definition(
                    RecordDefinition(
                        key, str(base or ""), fields, source, kind, type_name
                    )
                )
            else:
                self._pending_fields.append(
                    (key, _mark_fresh(value) if override else value, source)
                )
        if override:
            self._flush_pending()

    def add_file(self, filepath, *, override=False):
        filepath = os.fspath(filepath)
        text = read_bytes(filepath).decode("utf-8-sig")
        lowered = filepath.casefold()
        if lowered.endswith(".tweak"):
            self.add_tweak_text(text, filepath, override=override)
        elif lowered.endswith((".yaml", ".yml")):
            self.add_yaml_text(text, filepath, override=override)
        else:
            raise ValueError(f"Unsupported tweak source: {filepath}")

    def finalize(self):
        self._flush_pending()

    def adopt_compiled_inline_names(self, compiled):
        """Names the inline records of .tweak sources as the compiled game TweakDB does"""
        renamed_records = 0
        for record_id, definitions in list(self._definitions.items()):
            if not any(definition.source_kind == "tweak" for definition in definitions):
                continue
            count = sum(
                _inline_count(value)
                for definition in definitions
                if definition.source_kind == "tweak"
                for value in definition.fields.values()
            )
            if not count:
                continue
            candidates = {
                tweakdb_id(f"{record_id}_inline{index}"): f"{record_id}_inline{index}"
                for index in range(count + 16)
            }
            named = {}

            def rewrite(owner, field, value, source, slot=None):
                if isinstance(value, FieldUpdate):
                    return FieldUpdate(
                        value.operation, rewrite(owner, field, value.value, source)
                    )
                if isinstance(value, list):
                    targets = compiled.foreign_keys(f"{owner}.{field}") or ()
                    names = [
                        candidates[target] for target in targets if target in candidates
                    ]
                    names.reverse()
                    result = []
                    for item in value:
                        if isinstance(item, dict) and names:
                            result.append(
                                rewrite(owner, field, item, source, slot=names.pop())
                            )
                        else:
                            result.append(item)
                    return result
                if not isinstance(value, dict):
                    return value
                name = (
                    slot
                    if slot is not None
                    else candidates.get(compiled.foreign_key(f"{owner}.{field}"))
                )
                if name is None:
                    return value
                fields = {
                    key: rewrite(name, key, child, source)
                    for key, child in value.items()
                    if key not in _ATTRIBUTE_KEYS
                }
                named.setdefault(name, []).append(
                    RecordDefinition(
                        name,
                        str(value.get("$base", "") or ""),
                        fields,
                        source,
                        "tweak-inline",
                        str(value.get("$type", "") or ""),
                    )
                )
                return name

            rewritten = []
            for definition in definitions:
                if definition.source_kind != "tweak":
                    rewritten.append(definition)
                    continue
                fields = {
                    key: rewrite(record_id, key, value, definition.source)
                    for key, value in definition.fields.items()
                }
                rewritten.append(
                    RecordDefinition(
                        definition.record_id,
                        definition.base,
                        fields,
                        definition.source,
                        definition.source_kind,
                        definition.type_name,
                    )
                )
            if not named:
                continue
            for provisional in self._provisional_inline.pop(record_id, ()):
                self._definitions.pop(provisional, None)
            self._definitions[record_id] = rewritten
            for name, inline_definitions in named.items():
                self._definitions.setdefault(name, []).extend(inline_definitions)
            renamed_records += 1
        self._cache.clear()
        return renamed_records

    def has_record(self, record_id, current=""):
        return self._lookup_id(record_id, current) is not None

    def resolve(self, record_id, current=""):
        resolved_id = self._lookup_id(record_id, current)
        if resolved_id is None:
            raise KeyError(f"Tweak record not found: {record_id}")
        return self._resolve_record(resolved_id, ())

    def resolve_link(self, value, current=""):
        if isinstance(value, str):
            resolved_id = self._lookup_id(value, current)
            if resolved_id is None:
                raise KeyError(f"Tweak record not found: {value}")
            return self._resolve_record(resolved_id, ()).fields
        if isinstance(value, dict):
            return self._resolve_mapping({}, value, current, ())
        raise TypeError(
            f"Expected a record reference or inline record, got {type(value).__name__}"
        )

    def link_fields(self, value, current=""):
        """The fields of an inline record, or of the record a name refers to"""
        if isinstance(value, dict):
            return value
        if not isinstance(value, str) or not value:
            return {}
        try:
            return self.resolve_link(value, current)
        except (KeyError, TypeError):
            return {}

    def records_for_entity(self, entity_path):
        """The records whose entityTemplatePath is the entity, by name"""
        entity_key = depot_path_key(entity_path)
        matches = []
        for record_id in self._definitions:
            try:
                record = self._resolve_record(record_id, ())
            except (KeyError, TweakParseError):
                continue
            template = record.fields.get("entityTemplatePath")
            if isinstance(template, str) and depot_path_key(template) == entity_key:
                matches.append(record)
        matches.sort(key=lambda record: record.record_id.casefold())
        return tuple(matches)

    def base_record(self, record_id):
        """The record that record_id inherits from, or '' when it has none"""
        base = ""
        for definition in self._definitions.get(record_id) or ():
            name = definition.base or (
                definition.fields.get("$base")
                if isinstance(definition.fields, dict)
                else ""
            )
            if name:
                base = self._lookup_id(name, record_id) or base
        return base

    def _flush_pending(self):
        for key, value, source in self._pending_fields:
            owner = self._field_owner(key)
            if owner:
                field_path = key[len(owner) + 1 :]
                fields = self._nested_field(field_path, value)
                self._add_definition(
                    RecordDefinition(owner, "", fields, source, "yaml-field")
                )
                continue
            if isinstance(value, dict):
                self._add_definition(RecordDefinition(key, "", value, source, "yaml"))
            else:
                self.diagnostics.append(
                    f"Unresolved field fragment {key} from {source}"
                )
        self._pending_fields.clear()
        self._cache.clear()

    def _field_owner(self, key):
        """The longest record name that key extends with a field path"""
        end = len(key)
        while True:
            end = key.rfind(".", 0, end)
            if end <= 0:
                return ""
            if key[:end] in self._definitions:
                return key[:end]

    def _resolve_record(self, record_id, stack):
        cached = self._cache.get(record_id)
        if cached is not None:
            return cached
        if record_id in stack:
            raise TweakParseError(
                "Tweak inheritance cycle: " + " -> ".join((*stack, record_id))
            )
        definitions = self._definitions.get(record_id)
        if not definitions:
            raise KeyError(f"Tweak record not found: {record_id}")
        fields = {}
        sources = []
        type_name = ""
        next_stack = (*stack, record_id)
        for definition in definitions:
            if definition.base:
                base_id = self._lookup_id(definition.base, record_id)
                if base_id is not None:
                    base_record = self._resolve_record(base_id, next_stack)
                    fields = copy.deepcopy(base_record.fields)
                    sources.extend(base_record.sources)
                else:
                    self.diagnostics.append(
                        f"Unresolved base {definition.base} for {record_id} from {definition.source}"
                    )
            fields = self._resolve_mapping(
                fields, definition.fields, record_id, next_stack
            )
            sources.append(definition.source)
            type_name = definition.type_name or type_name
        result = ResolvedRecord(
            record_id, fields, tuple(dict.fromkeys(sources)), type_name
        )
        self._cache[record_id] = result
        return result

    def _resolve_mapping(self, base, overlay, current, stack):
        result = copy.deepcopy(base) if isinstance(base, dict) else {}
        inline_base = overlay.get("$base") if isinstance(overlay, dict) else None
        if inline_base:
            base_id = self._lookup_id(inline_base, current)
            if base_id is not None:
                result = copy.deepcopy(self._resolve_record(base_id, stack).fields)
        for key, value in overlay.items():
            if key in _ATTRIBUTE_KEYS:
                continue
            existing = result.get(key)
            result[key] = self._resolve_value(existing, value, current, stack)
        return result

    def _resolve_value(self, existing, value, current, stack):
        if isinstance(value, FieldUpdate):
            if value.operation != "append":
                raise TweakParseError(f"Unsupported field operation: {value.operation}")
            additions = value.value if isinstance(value.value, list) else [value.value]
            return self._apply_list(
                existing,
                [TaggedValue("append", item) for item in additions],
                current,
                stack,
            )
        if isinstance(value, dict):
            if value.get(FRESH_KEY):
                return self._resolve_mapping({}, value, current, stack)
            base_mapping = existing
            if isinstance(existing, str):
                existing_id = self._lookup_id(existing, current)
                if existing_id is not None:
                    base_mapping = self._resolve_record(existing_id, stack).fields
            return self._resolve_mapping(base_mapping, value, current, stack)
        if isinstance(value, list):
            return self._apply_list(existing, value, current, stack)
        if isinstance(value, tuple):
            return tuple(
                self._resolve_value(None, item, current, stack) for item in value
            )
        return copy.deepcopy(value)

    def _apply_list(self, existing, values, current, stack):
        """A list assignment, or TweakXL mutations of the existing list"""
        operations = [value for value in values if isinstance(value, TaggedValue)]
        if not operations:
            return [
                self._resolve_value(None, value, current, stack) for value in values
            ]
        if len(operations) != len(values):
            self.diagnostics.append(
                f"{current}: a list mixes items and mutations; only the mutations apply"
            )
        unknown = [
            operation.operation
            for operation in operations
            if operation.operation not in LIST_TAGS
        ]
        if unknown:
            raise TweakParseError(f"Unsupported YAML tag operation: {unknown[0]}")

        def resolved(operation):
            return self._resolve_value(None, operation.value, current, stack)

        result = list(existing) if isinstance(existing, (list, tuple)) else []
        if any(operation.operation == "remove-all" for operation in operations):
            result = []
        removed = []
        for operation in operations:
            if operation.operation == "remove":
                item = resolved(operation)
                removed.append(item)
                if item in result:
                    result.remove(item)

        def insertions(single, unique, merged):
            items = []
            for operation in operations:
                if operation.operation in single:
                    item = resolved(operation)
                    if item in removed or (
                        operation.operation in unique
                        and (item in result or item in items)
                    ):
                        continue
                    items.append(item)
            for operation in operations:
                if operation.operation in merged:
                    for item in self._list_flat(operation.value, current, stack):
                        if (
                            item not in result
                            and item not in items
                            and item not in removed
                        ):
                            items.append(item)
            return items

        prepended = insertions(
            ("prepend", "prepend-once"), ("prepend-once",), ("prepend-from",)
        )
        result = prepended + result
        result.extend(
            insertions(
                ("append", "append-once"), ("append-once",), ("append-from", "merge")
            )
        )
        return result

    def _list_flat(self, flat_name, current, stack):
        """The items of the list field a -from/!merge tag names as Record.field"""
        name = str(flat_name or "")
        owner = self._field_owner(name)
        if not owner:
            self.diagnostics.append(
                f"{current}: cannot merge {name}, no such list field"
            )
            return []
        value = self._resolve_record(owner, stack).fields
        for part in name[len(owner) + 1 :].split("."):
            value = value.get(part) if isinstance(value, dict) else None
        if not isinstance(value, (list, tuple)):
            self.diagnostics.append(f"{current}: cannot merge {name}, it is not a list")
            return []
        return copy.deepcopy(list(value))

    def _lookup_id(self, value, current=""):
        name = str(value or "")
        if name in self._definitions:
            return name
        if "." not in name and current and "." in current:
            candidate = current.split(".", 1)[0] + "." + name
            if candidate in self._definitions:
                return candidate
        return None

    def _add_definition(self, definition):
        self._definitions.setdefault(definition.record_id, []).append(definition)
        if definition.source_kind == "tweak":
            counter = [0]

            def register_inline(value):
                if isinstance(value, dict):
                    inline_id = f"{definition.record_id}_inline{counter[0]}"
                    counter[0] += 1
                    inline_base = str(value.get("$base", "") or "")
                    inline_type = str(value.get("$type", "") or "")
                    inline_fields = {
                        key: child
                        for key, child in value.items()
                        if key not in _ATTRIBUTE_KEYS
                    }
                    self._definitions.setdefault(inline_id, []).append(
                        RecordDefinition(
                            inline_id,
                            inline_base,
                            inline_fields,
                            definition.source,
                            "tweak-inline",
                            inline_type,
                        )
                    )
                    self._provisional_inline.setdefault(
                        definition.record_id, []
                    ).append(inline_id)
                    for child in inline_fields.values():
                        register_inline(child)
                    return
                if isinstance(value, (list, tuple)):
                    for child in value:
                        register_inline(child)
                if isinstance(value, FieldUpdate):
                    register_inline(value.value)

            for child in definition.fields.values():
                register_inline(child)
        self._cache.clear()

    @staticmethod
    def _nested_field(path, value):
        result = value
        for segment in reversed(path.split(".")):
            result = {segment: result}
        return result


def _mark_fresh(value):
    """Override values"""
    if isinstance(value, dict):
        marked = {key: _mark_fresh(child) for key, child in value.items()}
        if "$base" not in value:
            marked[FRESH_KEY] = True
        return marked
    if isinstance(value, list):
        return [_mark_fresh(item) for item in value]
    if isinstance(value, TaggedValue):
        return TaggedValue(value.operation, _mark_fresh(value.value))
    if isinstance(value, FieldUpdate):
        return FieldUpdate(value.operation, _mark_fresh(value.value))
    return value


def _mark_fresh_fields(fields):
    return {key: _mark_fresh(value) for key, value in fields.items()}


def _inline_count(value):
    """Inline records in a field value, nested ones included"""
    if isinstance(value, dict):
        return 1 + sum(_inline_count(child) for child in value.values())
    if isinstance(value, (list, tuple)):
        return sum(_inline_count(child) for child in value)
    if isinstance(value, FieldUpdate):
        return _inline_count(value.value)
    return 0


def tweakxl_load_order(paths, root):
    """Tweak files below root in the order TweakXL reads them"""

    def components(path):
        relative = relative_local_path(path, root) or os.path.basename(path)
        return [part.upper() for part in relative.replace("\\", "/").split("/")]

    ordered = sorted((os.fspath(path) for path in paths), key=components)
    first = [path for path in ordered if os.path.basename(path)[:1] in "_#$!"]
    last = [path for path in ordered if os.path.basename(path)[:1] == "^"]
    middle = [path for path in ordered if path not in first and path not in last]
    return first + middle + last


def load_tweak_database(paths):
    database = TweakDatabase()
    ranked = sorted(
        (os.fspath(path) for path in paths),
        key=lambda path: (
            0 if path.casefold().endswith(".tweak") else 1,
            path.casefold(),
        ),
    )
    for path in ranked:
        # One malformed base file is skipped and reported, as an override would be, rather than ending the load.
        try:
            database.add_file(path)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            database.diagnostics.append(f"Skipped {path}: {error}")
    database.finalize()
    return database


_BASE_DATABASES = {}


def load_layered_tweak_database(
    base_paths, override_paths=(), compiled=None, *, base_key=None
):
    """Base sources, named against an optional compiled TweakDB, with override files applied in order"""
    signature = (base_key, id(compiled)) if base_key is not None else None
    cached = _BASE_DATABASES.get(signature) if signature is not None else None
    if cached is not None:
        base = cached[0]
    else:
        base = load_tweak_database(base_paths)
        if compiled is not None:
            base.adopt_compiled_inline_names(compiled)
        if signature is not None:
            _BASE_DATABASES.clear()
            # The compiled database is held so its id cannot be reused while the entry exists.
            _BASE_DATABASES[signature] = (base, compiled)
    database = base.copy()
    for path in override_paths:
        try:
            database.add_file(path, override=True)
        except (OSError, UnicodeDecodeError, ValueError) as error:
            database.diagnostics.append(f"Skipped {path}: {error}")
    database.finalize()
    return database
