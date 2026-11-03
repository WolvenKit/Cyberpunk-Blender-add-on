from __future__ import annotations

from .topology import GraphTopologyError, resolve


def constraint_leaves(reference, index):
    active = set()
    stack = [(reference, "root", False)]
    while stack:
        reference, path, leaving = stack.pop()
        node = resolve(reference, index)
        if not node:
            continue
        if leaving:
            active.remove(id(node))
            continue
        if node.get("$type") != "animDyngConstraintMulti":
            yield path, reference, node
            continue
        if id(node) in active:
            raise GraphTopologyError(f"Constraint tree contains a cycle at {path}")
        active.add(id(node))
        stack.append((reference, path, True))
        children = node.get("innerConstraints") or []
        stack.extend(
            (child, f"{path}/{i}", False)
            for i, child in reversed(list(enumerate(children)))
        )
