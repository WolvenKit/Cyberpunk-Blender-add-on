from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...assetio.paths import depot_path_key
from ...assetio.values import cname_text, coerce_float, resource_path_text
from .document import DEFAULT_STATE, WidgetRecord, color

_INTEGER_TYPES = frozenset(
    {"Int8", "Int16", "Int32", "Int64", "Uint8", "Uint16", "Uint32", "Uint64"}
)
_FLOAT_TYPES = frozenset({"Float", "Double"})


@dataclass(frozen=True, slots=True)
class Reference:
    """A property whose value is another property's, looked up in the default state"""

    path: str


@dataclass(frozen=True, slots=True)
class StyleResource:
    path: str
    properties: dict[tuple[str, str], Any]
    imports: tuple[str, ...]
    states: tuple[str, ...] = ()


def style_value(payload: Any) -> Any:
    """A typed style property value"""
    if not isinstance(payload, dict):
        return payload
    kind = str(payload.get("$type") or "")
    inner = payload.get("Value", payload)
    if kind == "inkStylePropertyReference":
        return Reference(
            cname_text(inner.get("referencedPath") if isinstance(inner, dict) else "")
        )
    if kind in ("HDRColor", "Color"):
        return color(payload)
    if kind in _INTEGER_TYPES:
        return int(coerce_float(inner, 0.0))
    if kind in _FLOAT_TYPES:
        return coerce_float(inner, 0.0)
    if kind == "Bool":
        return bool(coerce_float(inner, 0.0))
    if kind in ("CName", "String"):
        return cname_text(inner)
    if kind.startswith(("raRef:", "rRef:")):
        return resource_path_text(inner)
    return inner


def read_style(document: dict, path: str = "") -> StyleResource:
    resource = (
        document.get("Data", {}).get("RootChunk", {})
        if isinstance(document, dict)
        else {}
    )
    properties: dict[tuple[str, str], Any] = {}
    states: dict[str, None] = {}
    for style in resource.get("styles") or ():
        if not isinstance(style, dict):
            continue
        state = cname_text(style.get("state")) or DEFAULT_STATE
        states.setdefault(state)
        for entry in style.get("properties") or ():
            if isinstance(entry, dict) and (
                property_path := cname_text(entry.get("propertyPath"))
            ):
                properties.setdefault(
                    (state, property_path), style_value(entry.get("value"))
                )
    imports = tuple(
        imported
        for entry in resource.get("styleImports") or ()
        if (imported := resource_path_text(entry))
    )
    return StyleResource(str(path), properties, imports, tuple(states))


@dataclass(slots=True)
class StyleSheet:
    """The style resources a widget library uses, by depot path"""

    resources: dict[str, StyleResource] = field(default_factory=dict)
    fallback_states: tuple[str, ...] = ()

    def add(self, resource: StyleResource) -> bool:
        """Add resource, or return False when one with its path is already present"""
        key = depot_path_key(resource.path)
        if key in self.resources:
            return False
        self.resources[key] = resource
        return True

    def _search(
        self, key: str, property_path: str, state: str, visited: set
    ) -> tuple[bool, Any]:
        if key in visited or key not in self.resources:
            return False, None
        visited.add(key)
        resource = self.resources[key]
        candidates = (state, DEFAULT_STATE)
        if self.fallback_states:
            candidates += self.fallback_states + resource.states
        for candidate in dict.fromkeys(candidates):
            if (candidate, property_path) in resource.properties:
                return True, resource.properties[(candidate, property_path)]
        for imported in resource.imports:
            found, value = self._search(
                depot_path_key(imported), property_path, state, visited
            )
            if found:
                return found, value
        return False, None

    def value(
        self, style_path: str, property_path: str, state: str = DEFAULT_STATE
    ) -> Any:
        """The value of property_path under the style at style_path, or None"""
        key = depot_path_key(style_path)
        followed = set()
        while True:
            found, value = self._search(key, property_path, state, set())
            if not found:
                return None
            if not isinstance(value, Reference):
                return value
            if value.path in followed or not value.path:
                return None
            followed.add(property_path)
            property_path, state = value.path, DEFAULT_STATE


def widget_style_path(widget: WidgetRecord) -> str:
    """The style the widget's bindings resolve in"""
    current = widget
    while current is not None:
        if current.style_path:
            return current.style_path
        current = current.parent
    return ""


def bound_values(
    widget: WidgetRecord, sheet: StyleSheet
) -> tuple[dict[str, Any], list[str]]:
    """(bound values by property name, unresolved style paths) for the widget's property bindings"""
    style_path = widget_style_path(widget)
    values: dict[str, Any] = {}
    unresolved: list[str] = []
    for property_name, path in widget.bindings:
        value = sheet.value(style_path, path, widget.state) if style_path else None
        if value is None:
            unresolved.append(path)
        else:
            values[property_name] = value
    return values, unresolved
