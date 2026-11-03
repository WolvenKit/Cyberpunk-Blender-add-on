from __future__ import annotations

from bpy.types import UIList

TYPE_ICONS = {
    "MESH": "MESH_DATA",
    "SKINNED": "ARMATURE_DATA",
    "GARMENT": "MOD_CLOTH",
    "PHYSICAL": "PHYSICS",
    "PHYSICAL_SKINNED": "PHYSICS",
}
# Each component list's row depths by its appearance state's pointer, found by its last filter_items.
_DEPTHS: dict[int, list[int]] = {}


def _depth(item, by_name) -> int:
    depth, seen, current = 0, {item.name}, item
    while current.attach_target in by_name and current.attach_target not in seen:
        seen.add(current.attach_target)
        current = by_name[current.attach_target]
        depth += 1
    return depth


def _depths(items) -> list[int]:
    """How deep each row sits under the components it attaches to"""
    by_name = {item.name: item for item in items if not item.removed}
    return [_depth(item, by_name) for item in items]


def _tree_order(items) -> list[int]:
    """Rows ordered by what they attach to, each component's attached components right under it"""
    live = [index for index, item in enumerate(items) if not item.removed]
    by_name = {items[index].name: index for index in live}
    children: dict[str, list[int]] = {}
    roots = []
    for index in live:
        target = items[index].attach_target
        if target in by_name and target != items[index].name:
            children.setdefault(target, []).append(index)
        else:
            roots.append(index)
    roots.sort(
        key=lambda index: (
            items[index].attach_target.casefold(),
            items[index].name.casefold(),
        )
    )
    ordered, seen = [], set()

    def visit(index):
        if index in seen:
            return
        seen.add(index)
        ordered.append(index)
        for child in sorted(
            children.get(items[index].name, ()),
            key=lambda value: items[value].name.casefold(),
        ):
            visit(child)

    for index in roots + live:
        visit(index)
    ordered.extend(index for index in range(len(items)) if index not in seen)
    order = [0] * len(items)
    for position, index in enumerate(ordered):
        order[index] = position
    return order


class CP77_UL_EntityComponents(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        depths = _DEPTHS.get(data.as_pointer())
        if depths is None or len(depths) != len(data.components):
            depths = _DEPTHS[data.as_pointer()] = _depths(data.components)
        row = layout.row(align=True)
        depth = depths[index]
        if depth:
            row.separator(factor=1.5 * depth)
        row.label(text=item.name, icon=TYPE_ICONS.get(item.type_key, "OBJECT_DATA"))
        row.prop(
            item,
            "enabled",
            text="",
            emboss=False,
            icon="HIDE_OFF" if item.enabled else "HIDE_ON",
        )

    def filter_items(self, context, data, propname):
        items = getattr(data, propname)
        _DEPTHS[data.as_pointer()] = _depths(items)
        needle = self.filter_name.casefold()
        flags = [
            self.bitflag_filter_item
            if not item.removed and (not needle or needle in item.name.casefold())
            else 0
            for item in items
        ]
        return flags, _tree_order(items)


class CP77_UL_EntityIssues(UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        layout.label(text=item.message, icon="ERROR")


ENTITY_LIST_CLASSES = (CP77_UL_EntityComponents, CP77_UL_EntityIssues)
