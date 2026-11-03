from __future__ import annotations

from dataclasses import dataclass

import bpy


@dataclass(frozen=True)
class PathLevel:
    tree_name: str
    node_name: str  # The container node in the level above; empty for the root.
    label: str


# Editor area key -> the deepest path entered there.
_TRAILS: dict[int, tuple[PathLevel, ...]] = {}


def _container(parent, tree):
    return next(
        (node for node in parent.nodes if getattr(node, "node_tree", None) == tree),
        None,
    )


def levels(space) -> tuple[PathLevel, ...]:
    result, parent = [], None
    for item in space.path:
        tree = item.node_tree
        node = _container(parent, tree) if parent is not None else None
        label = (node.label or node.name) if node is not None else tree.name
        result.append(
            PathLevel(tree.name, node.name if node is not None else "", label)
        )
        parent = tree
    return tuple(result)


def trail(
    area_key: int, current: tuple[PathLevel, ...]
) -> tuple[tuple[PathLevel, bool], ...]:
    """current and, marked True, the remembered levels below it while current leads to them"""
    remembered = _TRAILS.get(area_key, ())
    if len(remembered) > len(current) and remembered[: len(current)] == current:
        return tuple((level, False) for level in current) + tuple(
            (level, True) for level in remembered[len(current) :]
        )
    _TRAILS[area_key] = current
    return tuple((level, False) for level in current)


def go_to(space, area_key: int, index: int) -> None:
    """Show level index of the editor's trail, going up or back down along it"""
    target = [level for level, _remembered in trail(area_key, levels(space))][
        : max(0, index) + 1
    ]
    trees = [bpy.data.node_groups.get(level.tree_name) for level in target]
    if not trees or trees[0] is None:
        return
    space.path.start(trees[0])
    for parent, level, tree in zip(trees, target[1:], trees[1:]):
        node = parent.nodes.get(level.node_name) if parent is not None else None
        if tree is None or node is None:
            break
        space.path.append(tree, node=node)


def drop_missing() -> None:
    """Cut every remembered trail at the first level whose tree or container node is gone"""
    for key, remembered in tuple(_TRAILS.items()):
        kept, parent = [], None
        for level in remembered:
            tree = bpy.data.node_groups.get(level.tree_name)
            if tree is None or (
                parent is not None and parent.nodes.get(level.node_name) is None
            ):
                break
            kept.append(level)
            parent = tree
        _TRAILS[key] = tuple(kept)
