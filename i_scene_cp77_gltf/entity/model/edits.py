from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ComponentKey:
    """A component of the source appearance"""

    name: str
    cruid: str


@dataclass(frozen=True, slots=True)
class Binding:
    """What a component attaches to"""

    target: str
    slot: str = ""


@dataclass(frozen=True, slots=True)
class ComponentEdit:
    """A mesh component as it should be exported"""

    key: ComponentKey | None
    template: ComponentKey | None
    name: str
    enabled: bool
    type_key: str
    mesh: str
    mesh_appearance: str
    chunk_mask: int
    attach: Binding | None
    skin: str


@dataclass(frozen=True, slots=True)
class AppearanceEdit:
    """One appearance as it should be exported"""

    name: str
    source_name: str
    entry_name: str
    components: tuple[ComponentEdit, ...]
    removed: frozenset[ComponentKey]


@dataclass(frozen=True, slots=True)
class EntityEdit:
    ent_path: str
    app_path: str
    appearances: tuple[AppearanceEdit, ...]
    removed_appearances: frozenset[str]
    default_appearance: str


@dataclass(frozen=True, slots=True)
class ExportTarget:
    ent_path: str
    app_path: str
    overwrite: bool
    all_appearances: bool


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    appearance: str
    component: str
    message: str
