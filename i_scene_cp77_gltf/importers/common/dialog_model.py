from __future__ import annotations

import json
from dataclasses import dataclass, fields, replace
from math import ceil

from ...assetio.values import json_object


@dataclass(frozen=True, slots=True)
class Category:
    name: str
    label: str
    choices: tuple[str, ...]


def balanced_rows(count, per_row=4):
    """Buttons per row, spread evenly over as few rows as hold count"""
    if count <= 0:
        return ()
    rows = ceil(count / per_row)
    base, extra = divmod(count, rows)
    return tuple(base + (index < extra) for index in range(rows))


def category_property(category):
    return f"category_{category.name}"


def effective_choices(categories, switched_on, ticked):
    """The ticked choices of the switched-on categories"""
    return frozenset(
        choice
        for category in categories
        if category.name in switched_on
        for choice in category.choices
        if len(category.choices) == 1 or choice in ticked
    )


def memory_json(state):
    payload = {}
    for field in fields(state):
        value = getattr(state, field.name)
        payload[field.name] = sorted(value) if isinstance(value, frozenset) else value
    return json.dumps(payload, separators=(",", ":"))


def read_memory(text, default, *, flags=(), names=None, sets=None):
    """default with each field of text that reads"""
    payload = json_object(text)
    valid = {}
    for name in flags:
        if isinstance(payload.get(name), bool):
            valid[name] = payload[name]
    for name, allowed in (names or {}).items():
        value = payload.get(name)
        if isinstance(value, str) and value in allowed:
            valid[name] = value
    for name, allowed in (sets or {}).items():
        values = payload.get(name)
        if isinstance(values, list) and all(
            isinstance(value, str) and value in allowed for value in values
        ):
            valid[name] = frozenset(values)
    return replace(default, **valid)


def remembered_text(preferences, key):
    return str(getattr(preferences, key, "") or "")


def remember_text(preferences, key, text):
    import bpy

    setattr(preferences, key, text)
    # Blender writes dirty preferences on quit, so the choices survive a restart.
    bpy.context.preferences.is_dirty = True


def state_to_operator(properties, state, *, settings, categories, choices):
    """Set a dialog operator's properties from state"""
    for name in settings:
        setattr(properties, name, getattr(state, name))
    for category in categories:
        setattr(
            properties, category_property(category), category.name in state.categories
        )
    for choice in choices:
        setattr(properties, choice, choice in state.choices)


def state_from_operator(properties, state_type, *, settings, categories, choices):
    """The state_type a dialog operator's properties hold"""
    return state_type(
        **{name: getattr(properties, name) for name in settings},
        categories=frozenset(
            category.name
            for category in categories
            if getattr(properties, category_property(category))
        ),
        choices=frozenset(choice for choice in choices if getattr(properties, choice)),
    )
