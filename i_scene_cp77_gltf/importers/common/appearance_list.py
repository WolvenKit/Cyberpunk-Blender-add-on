from __future__ import annotations


def appearance_ticks(rows, remembered):
    """The ticks and the All Appearances toggle to show for a file"""
    if remembered is None:
        return frozenset({"default"}), False
    names, all_appearances = remembered
    return frozenset(name for name in names if name in rows), bool(all_appearances)


def appearance_request(selected, all_appearances, resolved_default):
    """The appearances to import"""
    if all_appearances:
        return ("ALL",)
    selected = tuple(dict.fromkeys(selected))
    covered = str(resolved_default or "").casefold() if "default" in selected else None
    names = tuple(
        name for name in selected if name == "default" or name.casefold() != covered
    )
    return names or ("default",)


def covered_appearances(rows, selected, all_appearances, resolved_default):
    """The rows the All Appearances toggle or a ticked "default" already brings"""
    if all_appearances:
        return frozenset(rows)
    if "default" in selected and resolved_default:
        key = str(resolved_default).casefold()
        return frozenset(
            row for row in rows if row != "default" and row.casefold() == key
        )
    return frozenset()
