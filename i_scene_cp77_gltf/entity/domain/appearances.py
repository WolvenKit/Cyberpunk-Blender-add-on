from __future__ import annotations

import copy

from ...assetio.paths import depot_path_key
from ...assetio.values import (
    cname_entry,
    cname_or_empty,
    cname_text,
    handle_data,
    resource_path_entry,
    resource_path_text,
)
from ..model.edits import EntityEdit
from .document import AppearanceDocument, EntityDocument


def _entries(app: AppearanceDocument) -> list:
    return app.root.setdefault("appearances", [])


def duplicate_appearance(app: AppearanceDocument, source: str, new_name: str) -> None:
    """Append a copy of source named new_name"""
    entry = next(
        (
            item
            for item in _entries(app)
            if cname_text(handle_data(item).get("name")) == source
        ),
        None,
    )
    if entry is None:
        raise KeyError(f"Appearance '{source}' is not in the .app")
    copied = app.handles.rehandle(entry)
    data = handle_data(copied)
    data["name"] = cname_entry(new_name, data.get("name"))
    _entries(app).append(copied)


def rename_appearance(app: AppearanceDocument, old: str, new: str) -> None:
    definition = app.definition(old)
    if definition is None:
        raise KeyError(f"Appearance '{old}' is not in the .app")
    definition["name"] = cname_entry(new, definition.get("name"))


def remove_appearance(app: AppearanceDocument, name: str) -> None:
    app.root["appearances"] = [
        item
        for item in _entries(app)
        if cname_text(handle_data(item).get("name")) != name
    ]


def keep_appearances(app: AppearanceDocument, names: frozenset[str]) -> None:
    app.root["appearances"] = [
        item
        for item in _entries(app)
        if cname_text(handle_data(item).get("name")) in names
    ]


def refresh_dependencies(
    app: AppearanceDocument, name: str, replaced: dict[str, str]
) -> None:
    """Point the appearance's dependency entries for swapped resources at the new paths"""
    definition = app.definition(name)
    if definition is None or not replaced:
        return
    replacements = {depot_path_key(old): new for old, new in replaced.items()}
    for key in ("resolvedDependencies", "looseDependencies"):
        for entry in definition.get(key) or ():
            new_path = replacements.get(depot_path_key(resource_path_text(entry)))
            if new_path is not None:
                entry.update(
                    resource_path_entry(new_path, entry.get("Flags", "Default"))
                )


def sync_entity_entries(
    ent: EntityDocument,
    edit: EntityEdit,
    *,
    app_depot: str,
    source_app_depot: str,
    keep_all: bool,
) -> None:
    """Make the .ent list the edit's appearances, pointing at app_depot"""
    root = ent.root
    entries = root.setdefault("appearances", [])
    by_appearance = {
        cname_text(entry.get("appearanceName")): entry for entry in entries
    }
    for appearance in edit.appearances:
        entry = by_appearance.get(appearance.name)
        if entry is None:
            source = by_appearance.get(appearance.source_name)
            if source is None:
                raise KeyError(
                    f"Appearance '{appearance.source_name}' has no entry in the entity"
                )
            entry = copy.deepcopy(source)
            entry["appearanceName"] = cname_entry(
                appearance.name, entry.get("appearanceName")
            )
            entries.append(entry)
            by_appearance[appearance.name] = entry
        if (
            appearance.entry_name
            and cname_text(entry.get("name")) != appearance.entry_name
        ):
            entry["name"] = cname_entry(appearance.entry_name, entry.get("name"))
    kept_names = {appearance.name for appearance in edit.appearances}
    root["appearances"] = [
        entry
        for entry in entries
        if cname_text(entry.get("appearanceName")) not in edit.removed_appearances
        and (keep_all or cname_text(entry.get("appearanceName")) in kept_names)
    ]
    source_key = depot_path_key(source_app_depot)
    for entry in root["appearances"]:
        resource = entry.get("appearanceResource")
        if depot_path_key(resource_path_text(resource)) == source_key:
            flags = (
                resource.get("Flags", "Default")
                if isinstance(resource, dict)
                else "Default"
            )
            entry["appearanceResource"] = resource_path_entry(app_depot, flags)
    entry_names = [cname_text(entry.get("name")) for entry in root["appearances"]]
    current = cname_or_empty(root.get("defaultAppearance"))
    if current == "random":
        return
    if edit.default_appearance and edit.default_appearance in entry_names:
        default = edit.default_appearance
    elif current and current not in entry_names:
        # The default's entry left the entity; the first remaining appearance takes its place.
        default = entry_names[0] if entry_names else ""
    else:
        return
    if default and default != current:
        root["defaultAppearance"] = cname_entry(default, root.get("defaultAppearance"))
