<<<<<<< Updated upstream
SOURCE_DEFAULT_APPEARANCE_TOKENS = frozenset(('', 'default', 'none', 'null'))
=======
from ...assetio.values import coerce_int

SOURCE_DEFAULT_APPEARANCE_TOKENS = frozenset(("", "default", "none", "null"))
>>>>>>> Stashed changes


def wrapped_string(value):
    if isinstance(value, dict):
<<<<<<< Updated upstream
        value = value.get('$value', value.get('value', ''))
    return str(value or '')
=======
        value = value.get("$value", value.get("value", ""))
    return str(value or "")
>>>>>>> Stashed changes


def is_source_default_appearance(value):
    return wrapped_string(value).strip().casefold() in (
        SOURCE_DEFAULT_APPEARANCE_TOKENS
    )


def _requested_appearance_names(appearances):
    requested = []
    for value in appearances or ():
        name = wrapped_string(value)
        if name:
            requested.append(name)
    return tuple(requested)


def _resolved_appearance_mappings(json_apps, appearances):
    requested = _requested_appearance_names(appearances)
<<<<<<< Updated upstream
    use_all = not requested or any(
        value.casefold() == 'all'
        for value in requested
    )
=======
    use_all = not requested or any(value.casefold() == "all" for value in requested)
>>>>>>> Stashed changes

    mappings = []
    resolved = {}
    unresolved = []
    if use_all:
        if isinstance(json_apps, dict):
            mappings.extend(
                (str(name), tuple(materials or ()))
                for name, materials in json_apps.items()
            )
<<<<<<< Updated upstream
        resolved['ALL'] = tuple(name for name, _ in mappings)
=======
        resolved["ALL"] = tuple(name for name, _ in mappings)
>>>>>>> Stashed changes
    else:
        for appearance in requested:
            resolved_name, materials, status = resolve_appearance_materials(
                json_apps,
                appearance,
            )
            if not resolved_name:
                unresolved.append((appearance, status))
                continue
            resolved[appearance] = resolved_name
            mappings.append((resolved_name, materials))
    return tuple(mappings), resolved, tuple(unresolved)


<<<<<<< Updated upstream
def resolve_appearance_materials(json_apps, appearance):
    """Resolve one authored appearance without falling back to another entry."""
    requested = wrapped_string(appearance)
    if isinstance(json_apps, dict) and requested in json_apps:
        return requested, tuple(json_apps.get(requested) or ()), 'exact'

    requested_folded = requested.casefold()
    matches = [
        (str(key), value)
        for key, value in (
            json_apps.items()
            if isinstance(json_apps, dict)
            else ()
        )
        if str(key).casefold() == requested_folded
    ]
    if len(matches) == 1:
        resolved, materials = matches[0]
        return resolved, tuple(materials or ()), 'casefold'
    if len(matches) > 1:
        return '', (), 'ambiguous_appearance'
    if is_source_default_appearance(requested):
        return '', (), 'source_default'
    if not isinstance(json_apps, dict) or not json_apps:
        return '', (), 'missing_appearance_data'
    return '', (), 'missing_appearance'


def select_material_names(json_apps, appearances):
    """Return materials required by the requested appearances."""
    if not isinstance(json_apps, dict) or not json_apps:
        return set(), {}, ()

    mappings, resolved, unresolved = _resolved_appearance_mappings(
        json_apps,
        appearances,
    )
    if 'ALL' in resolved:
        selected = {
            wrapped_string(material)
            for _appearance, materials in mappings
            for material in (materials or ())
            if wrapped_string(material)
        }
        return selected, resolved, unresolved

    selected = set()
    for _resolved_name, materials in mappings:
        selected.update(
            wrapped_string(material)
            for material in materials
            if wrapped_string(material)
        )
    return selected, resolved, unresolved


def requested_material_names_by_submesh(
        json_apps,
        appearances,
        source_material_names,
        submesh_indices=None,
        ):
    """Return source-first candidates keyed by authored submesh index."""
=======
def _named_appearance(json_apps, requested):
    """The (name, materials) entry named requested"""
    if isinstance(json_apps, dict) and requested in json_apps:
        return requested, tuple(json_apps.get(requested) or ())
    folded = requested.casefold()
    matches = [
        (str(key), tuple(value or ()))
        for key, value in (json_apps.items() if isinstance(json_apps, dict) else ())
        if str(key).casefold() == folded
    ]
    if len(matches) > 1:
        return ""
    return matches[0] if matches else None


def resolve_appearance_materials(json_apps, appearance):
    """Resolve one authored appearance"""
    requested = wrapped_string(appearance)
    entry = _named_appearance(json_apps, requested)
    if entry == "":
        return "", (), "ambiguous_appearance"
    if entry is not None:
        return entry[0], entry[1], "exact" if entry[0] == requested else "casefold"
    if is_source_default_appearance(requested):
        return "", (), "source_default"
    if not isinstance(json_apps, dict) or not json_apps:
        return "", (), "missing_appearance_data"
    fallback = _named_appearance(json_apps, "default")
    if fallback:
        return fallback[0], fallback[1], "missing_appearance_default"
    return "", (), "missing_appearance"


def requested_material_names_by_submesh(
    json_apps,
    appearances,
    source_material_names,
    submesh_indices=None,
):
    """Return source-first candidates keyed by authored submesh index"""
>>>>>>> Stashed changes
    sources = tuple(wrapped_string(value) for value in source_material_names)
    if submesh_indices is None:
        authored_indices = tuple(range(len(sources)))
    else:
        authored_indices = tuple(submesh_indices)
        if len(authored_indices) != len(sources):
            raise ValueError(
<<<<<<< Updated upstream
                "source_material_names and submesh_indices must have "
                "the same length"
            )
        normalized_indices = []
        for fallback_index, value in enumerate(authored_indices):
            try:
                authored_index = int(value)
            except (TypeError, ValueError):
                authored_index = fallback_index
=======
                "source_material_names and submesh_indices must have the same length"
            )
        normalized_indices = []
        for fallback_index, value in enumerate(authored_indices):
            authored_index = coerce_int(value, fallback_index, unwrap=False)
>>>>>>> Stashed changes
            if authored_index < 0:
                authored_index = fallback_index
            normalized_indices.append(authored_index)
        authored_indices = tuple(normalized_indices)

    planned = [[] for _ in sources]
    planned_seen = [set() for _ in sources]

    def append_unique(submesh_index, value):
        name = wrapped_string(value)
        if not name or submesh_index >= len(planned):
            return
        seen = planned_seen[submesh_index]
        if name in seen:
            return
        seen.add(name)
        planned[submesh_index].append(name)

    for index, source_name in enumerate(sources):
        append_unique(index, source_name)

    mappings, resolved, unresolved = _resolved_appearance_mappings(
        json_apps,
        appearances,
    )

    for _resolved_name, materials in mappings:
        for plan_index, authored_index in enumerate(authored_indices):
            if authored_index >= len(materials):
                continue
            append_unique(plan_index, materials[authored_index])

    return (
        tuple(tuple(names) for names in planned),
        resolved,
        unresolved,
    )
