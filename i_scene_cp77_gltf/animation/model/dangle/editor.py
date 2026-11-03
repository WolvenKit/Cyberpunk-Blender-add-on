from __future__ import annotations

import re
from collections import defaultdict, deque
from collections.abc import Iterable
from typing import Any

_TOKEN_ORDER = {
    "back": 0,
    "front": 1,
    "left": 0,
    "mid": 1,
    "right": 2,
    "top": 0,
    "bot": 1,
    "bottom": 1,
}


def payload_data(value: Any) -> dict | None:
    if isinstance(value, dict):
        if isinstance(value.get("Data"), dict):
            return value["Data"]
        if "$type" in value:
            return value
    return None


def _cname_text(value: Any) -> str:
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, dict):
            text = name.get("$value", "")
            return "" if text == "None" else str(text)
        text = value.get("$value", "")
        return "" if text == "None" else str(text)
    if isinstance(value, str):
        return "" if value == "None" else value
    return ""


def bone_name(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    return _cname_text(value) or _cname_text(value.get("name"))


def clean_name(value: str) -> str:
    text = "".join(ch if ch.isalnum() or ch in "_-" else "_" for ch in str(value or ""))
    return text.strip("_") or "item"


def strand_and_index(name: str, default_index: int = -1) -> tuple[str, int]:
    text = str(name or "")
    m = re.search(r"^(.*?)(?:_)?(\d+)$", text)
    if not m:
        return text, default_index
    return m.group(1), int(m.group(2))


def strand_sort_key(strand: str) -> tuple[int, int, int, str]:
    tokens = [
        t for t in str(strand or "").replace("-", "_").split("_") if t and t != "dyng"
    ]

    region = 99
    lateral = 99
    vertical = 99
    for token in tokens:
        if token in {"back", "front"}:
            region = min(region, _TOKEN_ORDER[token])
        elif token in {"left", "mid", "right"}:
            lateral = min(lateral, _TOKEN_ORDER[token])
        elif token in {"top", "bot", "bottom"}:
            vertical = min(vertical, _TOKEN_ORDER[token])
    return region, lateral, vertical, str(strand or "")


def particle_sort_key(
    name: str, default_index: int
) -> tuple[tuple[int, int, int, str], int, str, int]:
    strand, idx = strand_and_index(name, default_index)
    return (
        strand_sort_key(strand),
        idx if idx >= 0 else default_index,
        str(name or ""),
        default_index,
    )


def constraint_bones(data: dict) -> tuple[str, str]:
    ctype = str(data.get("$type", ""))
    if ctype.endswith("ConstraintLink"):
        return bone_name(data.get("bone1")), bone_name(data.get("bone2"))
    if ctype.endswith("ConstraintCone"):
        return bone_name(data.get("coneAttachmentBone")), bone_name(
            data.get("constrainedBone")
        )
    found: list[str] = []
    for _key, value in data.items():
        if isinstance(value, dict) and value.get("$type") == "animTransformIndex":
            text = bone_name(value)
            if text:
                found.append(text)
        if len(found) >= 2:
            break
    return (found[0] if len(found) > 0 else "", found[1] if len(found) > 1 else "")


def constraint_summary(data: dict) -> str:
    short = (
        str(data.get("$type", "animDyngConstraint")).replace("animDyngConstraint", "")
        or "Constraint"
    )
    if short == "Link":
        lower = data.get("lengthLowerBoundRatioPercentage")
        upper = data.get("lengthUpperBoundRatioPercentage")
        if lower is not None and upper is not None:
            return f"{data.get('linkType', 'Link')} {lower:g}-{upper:g}%"
        return str(data.get("linkType", "Link"))
    if short == "Cone":
        ctype = data.get("constraintType", "Cone")
        angle = data.get("halfOfMaxApertureAngle")
        return f"{ctype} {angle:g}°" if isinstance(angle, (int, float)) else str(ctype)
    return short


def constraint_edge_labels(data: dict, bone_a: str, bone_b: str) -> tuple[str, str]:
    summary = constraint_summary(data)
    ctype = str(data.get("$type", "")).replace("animDyngConstraint", "") or "Constraint"
    if ctype == "Link":
        return f"to {bone_b or '?'}", f"from {bone_a or '?'}"
    return f"{summary} →", f"← {summary}"


def particle_components(
    particle_names: Iterable[str], edge_pairs: Iterable[tuple[str, str]]
) -> list[list[str]]:
    adj: dict[str, set] = defaultdict(set)
    all_names = set(particle_names)
    for a, b in edge_pairs:
        if a:
            all_names.add(a)
        if b:
            all_names.add(b)
        if a and b:
            adj[a].add(b)
            adj[b].add(a)
    seen = set()
    components: list[list[str]] = []
    for seed in sorted(all_names, key=lambda n: particle_sort_key(n, 0)):
        if seed in seen:
            continue
        q = deque([seed])
        seen.add(seed)
        comp = []
        while q:
            cur = q.popleft()
            comp.append(cur)
            for nxt in sorted(adj.get(cur, ()), key=lambda n: particle_sort_key(n, 0)):
                if nxt not in seen:
                    seen.add(nxt)
                    q.append(nxt)
        components.append(sorted(comp, key=lambda n: particle_sort_key(n, 0)))
    return components
