from __future__ import annotations

from collections.abc import Mapping

from ....assetio.values import cname_or_empty


def additional_transform_data(node_type, node):
    container = (
        node.get("additionalTransforms")
        if isinstance(node.get("additionalTransforms"), Mapping)
        else {}
    )
    entries = []
    for wrapper in container.get("entries") or ():
        entry = (
            wrapper.get("Data")
            if isinstance(wrapper, Mapping) and isinstance(wrapper.get("Data"), Mapping)
            else None
        )
        if not isinstance(entry, Mapping):
            continue
        info = (
            entry.get("transformInfo")
            if isinstance(entry.get("transformInfo"), Mapping)
            else {}
        )
        name = cname_or_empty(info.get("name"))
        if not name:
            continue
        entries.append(
            {
                "name": name,
                "parent": cname_or_empty(info.get("parentName")),
                "reference": info.get("referenceTransformLs") or {},
                "value": entry.get("value") or {},
            }
        )
    return {"entries": tuple(entries)}
