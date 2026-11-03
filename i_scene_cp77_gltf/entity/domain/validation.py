from __future__ import annotations

from collections import Counter

from ...assetio.handles import HandleIndex
from ...assetio.values import cname_text, resource_path_text
from ..model.component_types import SKINNED_TYPES, type_key
from ..model.edits import EntityEdit, ValidationIssue
from .document import (
    AppearanceDocument,
    EntityDocument,
    attach_targets,
    binding_of,
    component_name,
    rig_targets,
    skin_of,
)


def _dangling_handles(pair, handles):
    """Handle references anywhere in the component's two copies that no definition answers"""
    stack = [copy_ for copy_ in (pair.listed, pair.compiled) if copy_ is not None]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            if "HandleRefId" in current and not handles.resolve(current):
                yield str(current["HandleRefId"])
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)


def _cycle_issues(graph: dict[str, str]):
    reported = set()
    for start in graph:
        seen = []
        current = start
        while current in graph and current not in seen:
            seen.append(current)
            current = graph[current]
        if current == start and len(seen) > 1:
            first, second = seen[0], seen[1]
            pair = frozenset((first, second))
            if pair not in reported:
                reported.add(pair)
                yield first, f'"{first}" and "{second}" attach to each other'


def appearance_issues(
    app: AppearanceDocument,
    ent: EntityDocument,
    appearance: str,
    removed_names: frozenset[str] = frozenset(),
) -> set[ValidationIssue]:
    """Every problem in one appearance, introduced or not"""
    pairs = app.components(appearance)
    issues: set[ValidationIssue] = set()

    def report(component, message):
        issues.add(ValidationIssue(appearance, component, message))

    names = Counter(component_name(pair.listed) for pair in pairs)
    for name, count in names.items():
        if count > 1:
            report(name, f'Two components are named "{name}"')
    ids = Counter(
        str(pair.listed.get("id", "")) for pair in pairs if pair.listed.get("id")
    )
    for pair in pairs:
        cruid = str(pair.listed.get("id", ""))
        if cruid and ids[cruid] > 1:
            report(component_name(pair.listed), f"Two components share the id {cruid}")

    targets = dict(attach_targets(app, ent, appearance))
    rigs = set(rig_targets(app, ent, appearance))
    current_handles = HandleIndex.build(app.document)
    graph = {}
    for pair in pairs:
        component = pair.listed
        name = component_name(component)
        binding = binding_of(component, app.handles)
        if binding is not None:
            if binding.target in removed_names:
                report(
                    binding.target,
                    f'"{binding.target}" is attached to by "{name}"; reattach it first',
                )
            elif binding.target not in targets:
                report(
                    name,
                    f'Attach To "{binding.target}" doesn\'t exist in this appearance',
                )
            elif binding.slot and binding.slot not in targets[binding.target]:
                report(
                    name, f'Slot "{binding.slot}" doesn\'t exist on "{binding.target}"'
                )
            graph[name] = binding.target
        mesh_type = type_key(component.get("$type"))
        skin = skin_of(component, app.handles)
        if (
            skin
            and (mesh_type in SKINNED_TYPES or mesh_type is None)
            and skin not in rigs
        ):
            report(name, f'Deform With "{skin}" isn\'t a rig in this appearance')
        if mesh_type is not None:
            mesh = resource_path_text(component.get("mesh"))
            if not mesh.casefold().endswith(".mesh"):
                report(name, f'Mesh path "{mesh}" must end in .mesh')
        for handle_id in _dangling_handles(pair, current_handles):
            report(name, f"Binding handle {handle_id} doesn't resolve")
    for name, message in _cycle_issues(graph):
        report(name, message)
    return issues


def _duplicate_entry_names(ent: EntityDocument) -> set[str]:
    names = Counter(cname_text(entry.get("name")) for entry in ent.entries())
    return {name for name, count in names.items() if name and count > 1}


def validate(
    app: AppearanceDocument,
    ent: EntityDocument,
    edit: EntityEdit,
    *,
    source_app: AppearanceDocument,
    source_ent: EntityDocument | None = None,
) -> tuple[ValidationIssue, ...]:
    """The problems edit introduced into the patched app and ent"""
    issues: list[ValidationIssue] = []
    existing_duplicates = (
        _duplicate_entry_names(source_ent) if source_ent is not None else set()
    )
    for name in sorted(_duplicate_entry_names(ent) - existing_duplicates):
        issues.append(
            ValidationIssue("", "", f'Two appearances have the entry name "{name}"')
        )
    source_names = set(source_app.appearance_names())
    for appearance in edit.appearances:
        removed = frozenset(key.name for key in appearance.removed)
        found = appearance_issues(app, ent, appearance.name, removed)
        existing = (
            {
                (issue.component, issue.message)
                for issue in appearance_issues(source_app, ent, appearance.source_name)
            }
            if appearance.source_name in source_names
            else set()
        )
        issues.extend(
            issue for issue in found if (issue.component, issue.message) not in existing
        )
        if ent.entry_for(appearance.name) is None:
            issues.append(
                ValidationIssue(
                    appearance.name,
                    "",
                    f'Appearance "{appearance.name}" has no entry in the entity',
                )
            )
    return tuple(
        sorted(
            issues, key=lambda issue: (issue.appearance, issue.component, issue.message)
        )
    )
