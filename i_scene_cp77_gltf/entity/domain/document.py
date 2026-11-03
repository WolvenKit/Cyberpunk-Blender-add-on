from __future__ import annotations

from dataclasses import dataclass

from ...assetio.handles import HandleIndex
from ...assetio.values import cname_or_empty, cname_text, handle_data
from ..model.edits import Binding

RIG_COMPONENT_TYPE = "entAnimatedComponent"


@dataclass(frozen=True, slots=True)
class ComponentPair:
    """One component's listed and compiled copies"""

    listed: dict
    compiled: dict | None


def component_name(component: dict) -> str:
    return cname_text(component.get("name"))


def _pair_components(
    listed: list[dict], compiled: list[dict]
) -> tuple[ComponentPair, ...]:
    if len(listed) == len(compiled) and all(
        component_name(left) == component_name(right)
        for left, right in zip(listed, compiled)
    ):
        return tuple(
            ComponentPair(left, right) for left, right in zip(listed, compiled)
        )
    by_identity = {}
    for chunk in compiled:
        by_identity.setdefault((str(chunk.get("id", "")), component_name(chunk)), chunk)
    return tuple(
        ComponentPair(
            component,
            by_identity.get((str(component.get("id", "")), component_name(component))),
        )
        for component in listed
    )


class AppearanceDocument:
    def __init__(self, document: dict):
        self.document = document
        self.handles = HandleIndex.build(document)

    @property
    def root(self) -> dict:
        return self.document["Data"]["RootChunk"]

    def definitions(self) -> tuple[dict, ...]:
        return tuple(handle_data(entry) for entry in self.root.get("appearances") or ())

    def appearance_names(self) -> tuple[str, ...]:
        return tuple(
            cname_text(definition.get("name")) for definition in self.definitions()
        )

    def definition(self, name: str) -> dict | None:
        return next(
            (
                item
                for item in self.definitions()
                if cname_text(item.get("name")) == name
            ),
            None,
        )

    def package(self, name: str) -> dict | None:
        definition = self.definition(name)
        compiled = definition.get("compiledData") if definition is not None else None
        data = compiled.get("Data") if isinstance(compiled, dict) else None
        return data if isinstance(data, dict) else None

    def components(self, name: str) -> tuple[ComponentPair, ...]:
        definition = self.definition(name)
        if definition is None:
            return ()
        listed = [
            handle_data(component) for component in definition.get("components") or ()
        ]
        package = self.package(name)
        compiled = [
            chunk
            for chunk in (package or {}).get("Chunks") or ()
            if isinstance(chunk, dict)
        ]
        return _pair_components(listed, compiled)


class EntityDocument:
    def __init__(self, document: dict):
        self.document = document
        self.handles = HandleIndex.build(document)

    @property
    def root(self) -> dict:
        return self.document["Data"]["RootChunk"]

    def entries(self) -> tuple[dict, ...]:
        return tuple(self.root.get("appearances") or ())

    def entry_for(self, appearance_name: str) -> dict | None:
        return next(
            (
                entry
                for entry in self.entries()
                if cname_text(entry.get("appearanceName")) == appearance_name
            ),
            None,
        )

    def default_appearance(self) -> str:
        return cname_or_empty(self.root.get("defaultAppearance"))

    def root_components(self) -> tuple[dict, ...]:
        return tuple(
            handle_data(component) for component in self.root.get("components") or ()
        )


def binding_of(component: dict, handles: HandleIndex) -> Binding | None:
    data = handles.resolve(component.get("parentTransform"))
    target = cname_or_empty(data.get("bindName")) if data else ""
    if not target:
        return None
    return Binding(target, cname_or_empty(data.get("slotName")))


def skin_of(component: dict, handles: HandleIndex) -> str:
    data = handles.resolve(component.get("skinning"))
    return cname_or_empty(data.get("bindName")) if data else ""


def slot_names(component: dict) -> tuple[str, ...]:
    return tuple(
        name
        for slot in component.get("slots") or ()
        if isinstance(slot, dict)
        for name in (cname_or_empty(slot.get("slotName")),)
        if name
    )


def slot_bone(component: dict, slot: str) -> str:
    """The bone a slot of a slot component sits on, or ''"""
    for entry in component.get("slots") or ():
        if isinstance(entry, dict) and cname_or_empty(entry.get("slotName")) == slot:
            return cname_or_empty(entry.get("boneName"))
    return ""


def find_component(
    app: AppearanceDocument, ent: EntityDocument, appearance: str, name: str
) -> dict | None:
    """A component of the appearance or of the entity's root components, by name"""
    return next(
        (
            component
            for found, component in _appearance_and_root_components(
                app, ent, appearance
            )
            if found == name
        ),
        None,
    )


def _appearance_and_root_components(
    app: AppearanceDocument, ent: EntityDocument, appearance: str
):
    seen = set()
    for component in (
        *(pair.listed for pair in app.components(appearance)),
        *ent.root_components(),
    ):
        name = component_name(component)
        if name and name not in seen:
            seen.add(name)
            yield name, component


def attach_targets(
    app: AppearanceDocument, ent: EntityDocument, appearance: str
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Every component a component of appearance can attach to, with its slot names"""
    return tuple(
        (name, slot_names(component))
        for name, component in _appearance_and_root_components(app, ent, appearance)
    )


def rig_targets(
    app: AppearanceDocument, ent: EntityDocument, appearance: str
) -> tuple[str, ...]:
    """The rigs a skinned component of appearance can deform with"""
    return tuple(
        name
        for name, component in _appearance_and_root_components(app, ent, appearance)
        if component.get("$type") == RIG_COMPONENT_TYPE
    )
