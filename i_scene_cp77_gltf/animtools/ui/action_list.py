import bpy

from ...animation.model.clip.metadata import prefers_simd
from ...blender.action_metadata import action_is_additive
from ...blender.animation_context import active_armature
from ...core.log import get_logger, log_once
from ..model.additive import ActionListSlot
from ..runtime import additive_preview

_LOG = get_logger(__name__)


def _filtered_flags(actions, *, additive_only: bool, filter_name: str, bitflag: int):
    helper_funcs = bpy.types.UI_UL_list
    flags = [
        bitflag if action_is_additive(action) == additive_only else 0
        for action in actions
    ]
    if filter_name:
        name_flags = helper_funcs.filter_items_by_name(
            filter_name,
            bitflag,
            actions,
            "name",
            reverse=False,
        )
        flags = [flag if name_flag else 0 for flag, name_flag in zip(flags, name_flags)]
    return flags


def _simd_icon(action):
    return (
        "FORCE_MAGNETIC"
        if prefers_simd(action.get("optimizationHints", None))
        else "FORCE_CHARGE"
    )


def _additive_type_icon(action):
    animation_type = str(
        action.get("animationType", "AdditiveFromRefPose") or "AdditiveFromRefPose"
    )
    return {
        "AdditiveFromRefPose": "LINKED",
        "AdditiveFromFirstFrame": "KEYFRAME_HLT",
        "Additive": "ADD",
        "AdditiveWithoutFirstFrame": "UNLINKED",
    }.get(animation_type, "ADD")


def _selected(active_data, active_propname, index):
    try:
        return int(getattr(active_data, active_propname, -1)) == int(index)
    except (AttributeError, TypeError, ValueError) as error:
        log_once(
            _LOG,
            "DEBUG",
            ("_selected", type(error).__name__),
            "selected: fell back after %s",
            error,
            exc_info=True,
        )
        return False


def _draw_action_row(
    context,
    layout,
    item,
    active_data,
    active_propname,
    index,
    *,
    additive: bool,
    slot=None,
):
    obj = active_armature(context)
    if obj is None or not obj.animation_data:
        return

    selected = _selected(active_data, active_propname, index)
    row = layout.row(align=True)

    if slot is None:
        slot = ActionListSlot.from_selector(active_propname)
    if additive_preview.is_active(obj):
        active = additive_preview.uses_action(obj, item, slot_index=slot.preview_slot)
    else:
        active = obj.animation_data.action == item
    if active and context.screen is not None and context.screen.is_animation_playing:
        op = row.operator(
            "screen.animation_cancel", icon="PAUSE", text="", emboss=False
        )
        op.restore_frame = False
    else:
        icon = "PLAY" if selected else "TRIA_RIGHT"
        op = row.operator("cp77.set_animset", icon=icon, text="", emboss=False)
        op.name = item.name
        op.play = True
        op.additive_slot = int(slot)

    op = row.operator("cp77.set_animset", text=item.name, emboss=False)
    op.name = item.name
    op.play = False
    op.additive_slot = int(slot)

    if item.use_frame_range:
        row.prop(item, "use_cyclic", icon="CON_FOLLOWPATH", text="", emboss=False)

    row.operator(
        "cp77.toggle_simd", icon=_simd_icon(item), text="", emboss=False
    ).name = item.name

    if additive:
        row.operator(
            "cp77.cycle_additive_type",
            icon=_additive_type_icon(item),
            text="",
            emboss=False,
        ).name = item.name

    row.operator("cp77.delete_anims", icon="X", text="", emboss=False).name = item.name


class CP77_UL_AnimList(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        _draw_action_row(
            context, layout, item, active_data, active_propname, index, additive=False
        )

    def filter_items(self, context, data, propname):
        actions = getattr(data, propname)
        flags = _filtered_flags(
            actions,
            additive_only=False,
            filter_name=self.filter_name,
            bitflag=self.bitflag_filter_item,
        )
        order = (
            bpy.types.UI_UL_list.sort_items_by_name(actions, "name")
            if self.use_filter_sort_alpha
            else []
        )
        return flags, order


class CP77_UL_ClipList(bpy.types.UIList):
    """Every clip, normal and additive"""

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        additive = action_is_additive(item)
        slot = ActionListSlot.PRIMARY if additive else ActionListSlot.NORMAL
        _draw_action_row(
            context,
            layout,
            item,
            active_data,
            active_propname,
            index,
            additive=additive,
            slot=slot,
        )

    def filter_items(self, context, data, propname):
        actions = getattr(data, propname)
        if self.filter_name:
            flags = bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                actions,
                "name",
                reverse=False,
            )
        else:
            flags = [self.bitflag_filter_item] * len(actions)
        order = (
            bpy.types.UI_UL_list.sort_items_by_name(actions, "name")
            if self.use_filter_sort_alpha
            else []
        )
        return flags, order


class CP77_UL_AdditiveAnimList(bpy.types.UIList):
    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index
    ):
        if self.layout_type not in {"DEFAULT", "COMPACT"}:
            return
        _draw_action_row(
            context, layout, item, active_data, active_propname, index, additive=True
        )

    def filter_items(self, context, data, propname):
        actions = getattr(data, propname)
        flags = _filtered_flags(
            actions,
            additive_only=True,
            filter_name=self.filter_name,
            bitflag=self.bitflag_filter_item,
        )
        order = (
            bpy.types.UI_UL_list.sort_items_by_name(actions, "name")
            if self.use_filter_sort_alpha
            else []
        )
        return flags, order
