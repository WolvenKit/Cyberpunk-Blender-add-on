from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ...assetio.handles import HandleIndex
from ...assetio.values import (
    cname_text,
    coerce_float,
    coerce_int,
    resource_path_text,
    strict_handle_data,
    vector2,
)

DEFAULT_STATE = "Default"
_BUFFERS = ("packageData", "package")
# Widget types that size to their content unless they say otherwise.
_FIT_BY_DEFAULT = frozenset({"inkHorizontalPanelWidget", "inkVerticalPanelWidget"})


@dataclass(frozen=True, slots=True)
class Margin:
    left: float = 0.0
    top: float = 0.0
    right: float = 0.0
    bottom: float = 0.0

    @property
    def horizontal(self) -> float:
        return self.left + self.right

    @property
    def vertical(self) -> float:
        return self.top + self.bottom


@dataclass(frozen=True, slots=True)
class Layout:
    anchor: str = "TopLeft"
    anchor_point: tuple[float, float] = (0.0, 0.0)
    margin: Margin = Margin()
    padding: Margin = Margin()
    h_align: str = "Fill"
    v_align: str = "Fill"
    size_rule: str = "Fixed"
    size_coefficient: float = 1.0


@dataclass(frozen=True, slots=True)
class RenderTransform:
    """Translation in pixels, rotation in degrees, scale and shear about pivot (a fraction of the size)"""

    translation: tuple[float, float] = (0.0, 0.0)
    scale: tuple[float, float] = (1.0, 1.0)
    shear: tuple[float, float] = (0.0, 0.0)
    rotation: float = 0.0
    pivot: tuple[float, float] = (0.5, 0.5)


@dataclass(slots=True, eq=False)
class WidgetRecord:
    """One widget as authored"""

    type: str
    name: str
    path: tuple[int, ...]
    data: dict
    layout: Layout
    size: tuple[float, float]
    fit_to_content: bool
    visible: bool
    affects_layout_when_hidden: bool
    opacity: float
    tint: tuple[float, float, float, float]
    render: RenderTransform
    child_order: str
    child_margin: Margin
    style_path: str
    state: str
    bindings: tuple[tuple[str, str], ...]
    parent: WidgetRecord | None = None
    children: list[WidgetRecord] = field(default_factory=list)

    @property
    def is_compound(self) -> bool:
        return "children" in self.data

    @property
    def depth(self) -> int:
        return len(self.path)

    @property
    def label(self) -> str:
        """The widget's name path from the item root, for messages"""
        names, current = [], self
        while current is not None:
            names.append(current.name or "<unnamed>")
            current = current.parent
        return "/".join(reversed(names))


@dataclass(slots=True)
class LibraryItem:
    name: str
    index: int
    root: WidgetRecord
    widgets: list[WidgetRecord]
    root_resolution: str


def margin(value: Any) -> Margin:
    if not isinstance(value, dict):
        return Margin()
    return Margin(
        *(
            coerce_float(value.get(side), 0.0)
            for side in ("left", "top", "right", "bottom")
        )
    )


def color(
    value: Any, default=(1.0, 1.0, 1.0, 1.0)
) -> tuple[float, float, float, float]:
    """An HDRColor (floats) or Color (0-255) value, optionally wrapped in Value"""
    if isinstance(value, dict) and isinstance(value.get("Value"), dict):
        value = value["Value"]
    if not isinstance(value, dict):
        return tuple(float(component) for component in default)
    scale = 1.0 / 255.0 if value.get("$type") == "Color" else 1.0
    return tuple(
        coerce_float(value.get(key), default[index] / scale) * scale
        for index, key in enumerate(("Red", "Green", "Blue", "Alpha"))
    )


def _flag(data: dict, key: str, default: bool) -> bool:
    value = data.get(key, default)
    return bool(coerce_float(value, 1.0 if default else 0.0))


def _layout(value: Any) -> Layout:
    if not isinstance(value, dict):
        return Layout()
    return Layout(
        anchor=str(value.get("anchor") or "TopLeft"),
        anchor_point=vector2(value.get("anchorPoint")),
        margin=margin(value.get("margin")),
        padding=margin(value.get("padding")),
        h_align=str(value.get("HAlign") or "Fill"),
        v_align=str(value.get("VAlign") or "Fill"),
        size_rule=str(value.get("sizeRule") or "Fixed"),
        size_coefficient=coerce_float(value.get("sizeCoefficient"), 1.0),
    )


def _render(data: dict) -> RenderTransform:
    transform = data.get("renderTransform")
    transform = transform if isinstance(transform, dict) else {}
    return RenderTransform(
        translation=vector2(transform.get("translation")),
        scale=vector2(transform.get("scale"), (1.0, 1.0)),
        shear=vector2(transform.get("shear")),
        rotation=coerce_float(transform.get("rotation"), 0.0),
        pivot=vector2(data.get("renderTransformPivot"), (0.5, 0.5)),
    )


def _bindings(data: dict) -> tuple[tuple[str, str], ...]:
    manager = strict_handle_data(data.get("propertyManager"))
    return tuple(
        (cname_text(binding.get("propertyName")), cname_text(binding.get("stylePath")))
        for binding in manager.get("bindings") or ()
        if isinstance(binding, dict)
    )


def _record(
    data: dict, path: tuple[int, ...], parent: WidgetRecord | None
) -> WidgetRecord:
    style = strict_handle_data(data.get("style"))
    state = cname_text(data.get("state"))
    return WidgetRecord(
        type=str(data.get("$type") or ""),
        name=cname_text(data.get("name")),
        path=path,
        data=data,
        layout=_layout(data.get("layout")),
        size=vector2(data.get("size")),
        fit_to_content=_flag(
            data, "fitToContent", data.get("$type") in _FIT_BY_DEFAULT
        ),
        visible=_flag(data, "visible", True),
        affects_layout_when_hidden=_flag(data, "affectsLayoutWhenHidden", False),
        opacity=coerce_float(data.get("opacity"), 1.0),
        tint=color(data.get("tintColor")),
        render=_render(data),
        child_order=str(data.get("childOrder") or "Forward"),
        child_margin=margin(data.get("childMargin")),
        style_path=resource_path_text(style.get("styleResource")),
        state=state if state and state != "None" else DEFAULT_STATE,
        bindings=_bindings(data),
        parent=parent,
    )


def _tree_of(item: Any, buffer: str) -> dict | None:
    """The item instance (with rootWidget) a buffer holds, or None"""
    payload = item.get(buffer) if isinstance(item, dict) else None
    data = payload.get("Data") if isinstance(payload, dict) else None
    if not isinstance(data, dict):
        return None
    chunks = data.get("Chunks")
    if isinstance(chunks, list):
        tree = next((chunk for chunk in chunks if isinstance(chunk, dict)), None)
    else:
        embedded = data.get("File")
        tree = embedded.get("RootChunk") if isinstance(embedded, dict) else None
    return (
        tree
        if isinstance(tree, dict) and isinstance(tree.get("rootWidget"), dict)
        else None
    )


def _child_entries(data: dict, handles: HandleIndex) -> list:
    container = handles.resolve(data.get("children"))
    entries = container.get("children")
    return entries if isinstance(entries, list) else []


def widget_data(tree: dict, path: tuple[int, ...]) -> dict:
    """The widget object at child-index path in an item tree"""
    handles = HandleIndex.build(tree)
    data = handles.resolve(tree.get("rootWidget"))
    for index in path:
        entries = _child_entries(data, handles)
        if not 0 <= index < len(entries):
            raise KeyError(f"no widget at {tuple(path)}")
        data = handles.resolve(entries[index])
    if not data:
        raise KeyError(f"no widget at {tuple(path)}")
    return data


def _read_item(item: dict, index: int) -> LibraryItem | None:
    tree = next(
        (found for buffer in _BUFFERS if (found := _tree_of(item, buffer)) is not None),
        None,
    )
    if tree is None:
        return None
    handles = HandleIndex.build(tree)
    widgets: list[WidgetRecord] = []

    def build(
        data: dict, path: tuple[int, ...], parent: WidgetRecord | None
    ) -> WidgetRecord:
        record = _record(data, path, parent)
        widgets.append(record)
        for child_index, entry in enumerate(_child_entries(data, handles)):
            child = handles.resolve(entry)
            if child:
                record.children.append(build(child, path + (child_index,), record))
        return record

    root_data = handles.resolve(tree["rootWidget"])
    if not root_data:
        return None
    root = build(root_data, (), None)
    return LibraryItem(
        cname_text(item.get("name")),
        index,
        root,
        widgets,
        str(tree.get("rootResolution") or ""),
    )


@dataclass(slots=True)
class WidgetLibrary:
    path: str
    document: dict
    dependencies: tuple[str, ...]
    animation_path: str
    root_index: int
    item_names: tuple[str, ...]
    _items: list = field(default_factory=list, repr=False)
    _cache: dict = field(default_factory=dict, repr=False)

    def _entry(self, name: str) -> tuple[int, dict]:
        for index, item in enumerate(self._items):
            if isinstance(item, dict) and cname_text(item.get("name")) == name:
                return index, item
        raise KeyError(f"library item '{name}' not found")

    def item(self, name: str | None = None) -> LibraryItem:
        """The named item, or with no name the root definition item (else the first item that holds a tree)"""
        if name in self._cache:
            return self._cache[name]
        if name is not None:
            index, entry = self._entry(name)
            item = _read_item(entry, index)
            if item is None:
                raise ValueError(f"library item '{name}' holds no widget tree")
        else:
            order = [self.root_index] if 0 <= self.root_index < len(self._items) else []
            order += [index for index in range(len(self._items)) if index not in order]
            item = next(
                (
                    read
                    for index in order
                    if (read := _read_item(self._items[index], index)) is not None
                ),
                None,
            )
            if item is None:
                raise ValueError("the widget library holds no widget tree")
        self._cache[name] = item
        return item

    def item_trees(self, name: str) -> tuple[tuple[str, dict], ...]:
        """(buffer key, item tree) for every buffer of the named item that holds its widget tree"""
        _index, entry = self._entry(name)
        return tuple(
            (buffer, tree)
            for buffer in _BUFFERS
            if (tree := _tree_of(entry, buffer)) is not None
        )


def read_library(document: dict, path: str = "") -> WidgetLibrary:
    resource = (
        document.get("Data", {}).get("RootChunk", {})
        if isinstance(document, dict)
        else {}
    )
    items = resource.get("libraryItems")
    items = items if isinstance(items, list) else []
    dependencies = tuple(
        depot
        for entry in resource.get("externalDependenciesForInternalItems") or ()
        if (depot := resource_path_text(entry))
    )
    root_index = coerce_int(
        resource.get("rootDefinitionIndex", 0) or 0, 0, unwrap=False
    )
    return WidgetLibrary(
        path=str(path),
        document=document,
        dependencies=dependencies,
        animation_path=resource_path_text(resource.get("animationLibraryResRef")),
        root_index=root_index,
        item_names=tuple(
            cname_text(item.get("name")) for item in items if isinstance(item, dict)
        ),
        _items=items,
    )
