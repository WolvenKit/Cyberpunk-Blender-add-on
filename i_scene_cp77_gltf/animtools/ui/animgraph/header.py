from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph.navigation_path import drop_missing, levels, trail


def area_key(area) -> int:
    return int(area.as_pointer()) if area is not None else 0


def draw_header_path(self, context) -> None:
    space = context.space_data
    if (
        getattr(space, "tree_type", "") != ANIMGRAPH_TREE_ID
        or getattr(space, "node_tree", None) is None
    ):
        return
    drop_missing()
    current = levels(space)
    row = self.layout.row(align=True)
    if len(current) > 1:
        row.operator("redengine.exit_group", text="Exit", icon="LOOP_BACK")
    for index, (level, remembered) in enumerate(trail(area_key(context.area), current)):
        button = row.row(align=True)
        button.active = not remembered
        icon = "NODETREE" if index == 0 else "NONE"
        button.operator(
            "redengine.go_to_level", text=level.label, icon=icon
        ).index = index
