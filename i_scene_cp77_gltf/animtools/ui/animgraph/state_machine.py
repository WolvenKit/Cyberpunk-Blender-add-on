import bpy

from ....animation.model.animgraph import sm_conditions
from ....animation.model.animgraph.constants import ANIMGRAPH_TREE_ID
from ....blender.animgraph import sm_edit, sm_records, sm_sockets
from ....blender.animgraph.property_ui import draw_scalar_target
from ....blender.animgraph.sm_records import ENTRY_RED_TYPE, _pseudo_node
from ....core.log import get_logger, log_once
from ...runtime import read_models
from ...services.animgraph.state_machine import context_state_machine

_LOG = get_logger(__name__)

_INDENT = 1.5


def _active_owner(context):
    node = getattr(context, "active_node", None)
    if not sm_edit.is_transition_owner(node):
        return None
    tree = getattr(node, "id_data", None)
    if getattr(tree, "bl_idname", ANIMGRAPH_TREE_ID) != ANIMGRAPH_TREE_ID:
        return None
    return node


def _condition_index(rec, cond) -> int:
    for index, other in enumerate(rec.conditions):
        if other == cond:
            return index
    return -1


def _draw_type_menu(layout, operator: str, index: int) -> None:
    """The catalogue grouped by family"""
    columns = layout.row()
    for family, shorts in sm_edit.CONDITION_FAMILIES:
        col = columns.column()
        col.label(text=family)
        for short in shorts:
            op = col.operator(operator, text=sm_edit.condition_label(short))
            op.short = short
            op.index = index


class REDENGINE_MT_sm_add_condition(bpy.types.Menu):
    """Condition types to add (into the group passed as red_sm_condition, else the root)"""

    bl_idname = "REDENGINE_MT_sm_add_condition"
    bl_label = "Add Condition"

    def draw(self, context):
        cond = getattr(context, "red_sm_condition", None)
        rec = getattr(context, "red_sm_transition", None)
        index = (
            _condition_index(rec, cond) if cond is not None and rec is not None else -1
        )
        _draw_type_menu(self.layout, "redengine.sm_add_condition", index)


class REDENGINE_MT_sm_change_condition(bpy.types.Menu):
    """Condition types to change the condition passed as red_sm_condition to"""

    bl_idname = "REDENGINE_MT_sm_change_condition"
    bl_label = "Change Condition Type"

    def draw(self, context):
        cond = getattr(context, "red_sm_condition", None)
        rec = getattr(context, "red_sm_transition", None)
        if cond is None or rec is None:
            self.layout.label(text="No condition")
            return
        _draw_type_menu(
            self.layout,
            "redengine.sm_change_condition_type",
            _condition_index(rec, cond),
        )


class REDENGINE_UL_transitions(bpy.types.UIList):
    """The rows of a state, Entry, Any State or (unowned rows) state machine node"""

    bl_idname = "REDENGINE_UL_transitions"

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index=0
    ):
        if item.list_name == sm_records.DEFAULT_LIST:
            layout.label(
                text=f"Default state: {sm_sockets.target_label(data, item)}",
                icon="HOME",
            )
            return
        layout.active = bool(item.enabled)
        try:
            text = sm_sockets.row_text(data, index)[0]
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("REDENGINE_UL_transitions.draw_item", type(error).__name__),
                "draw item: fell back after %s",
                error,
                exc_info=True,
            )
            text = "?"
        layout.label(text=text, icon="FORWARD")


def _draw_any_state_blend(layout, node):
    if not sm_edit.any_blend_editable(node):
        return
    box = layout.box()
    box.label(text="Any State blend")
    box.prop(node, "red_sm_any_interpolation", text="Curve")


def _draw_blend(layout, rec):
    box = layout.box()
    box.label(text="Blend")
    curve = box.row()
    curve.enabled = bool(rec.interpolator_type)
    curve.prop(rec, "interpolation_type", text="Curve")
    box.prop(rec, "can_request_inertialization", text="Can request inertialization")
    box.prop(rec, "support_blend_from_pose", text="Support blend from pose")


def _draw_condition(layout, rec):
    box = layout.box()
    box.label(text="Condition")
    if rec.condition_opaque_json:
        row = box.row(align=True)
        row.label(text=sm_records.OPAQUE_CONDITION_TEXT, icon="LINKED")
        op = row.operator("redengine.sm_remove_condition", text="", icon="X")
        op.index = 0
    elif len(rec.conditions) == 0:
        box.label(text=sm_conditions.NO_CONDITION_TEXT)
    for index, cond in enumerate(rec.conditions):
        entry = box.column(align=True)
        entry.context_pointer_set("red_sm_transition", rec)
        entry.context_pointer_set("red_sm_condition", cond)
        head = entry.row(align=True)
        if cond.depth:
            head.separator(factor=_INDENT * cond.depth)
        head.menu(
            "REDENGINE_MT_sm_change_condition", text=sm_edit.condition_label(cond.short)
        )
        if cond.short == sm_conditions.GROUP:
            head.menu("REDENGINE_MT_sm_add_condition", text="", icon="ADD")
        else:
            head.operator(
                "redengine.sm_wrap_condition", text="", icon="OUTLINER_COLLECTION"
            ).index = index
        head.operator("redengine.sm_remove_condition", text="", icon="X").index = index
        for field in cond.fields:
            row = entry.row(align=True)
            row.separator(factor=_INDENT * (cond.depth + 1))
            if field.value_kind == "RAW_JSON":
                continue
            draw_scalar_target(field, row, field.label or field.key)
    add = box.row()
    add.context_pointer_set("red_sm_transition", rec)
    add.menu("REDENGINE_MT_sm_add_condition", text="+ Add condition")


def _draw_advanced(layout, rec):
    header, body = layout.panel("REDENGINE_sm_transition_advanced", default_closed=True)
    header.label(text="Advanced")
    if body is None:
        return
    body.prop(rec, "anim_feature_name", text="Anim feature")
    body.prop(rec, "action_db_path", text="Action anim database")
    body.prop(rec, "is_out_transition_from_action", text="Out transition from action")


class REDENGINE_PT_transition_editor(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_transition_editor"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Graph"
    bl_label = "Transitions"

    @classmethod
    def poll(cls, context):
        space = getattr(context, "space_data", None)
        if space is None or getattr(space, "type", "") != "NODE_EDITOR":
            return False
        return _active_owner(context) is not None

    def draw(self, context):
        layout = self.layout
        node = _active_owner(context)
        if node is None:
            return
        if getattr(node, "red_type", "") == sm_records.ANY_RED_TYPE:
            _draw_any_state_blend(layout, node)

        row = layout.row()
        row.template_list(
            "REDENGINE_UL_transitions",
            "",
            node,
            "red_transitions",
            node,
            "red_transitions_index",
            rows=4,
        )
        records = node.red_transitions
        index = node.red_transitions_index
        is_default = (
            0 <= index < len(records)
            and records[index].list_name == sm_records.DEFAULT_LIST
        )
        col = row.column(align=True)
        if not sm_sockets.is_state_machine(node):
            col.operator("redengine.sm_add_transition", text="", icon="ADD")
        delete = col.row(align=True)
        delete.enabled = not is_default
        delete.operator("redengine.sm_delete_transition", text="", icon="REMOVE")
        col.separator()
        for direction, delta, icon in (("UP", -1, "TRIA_UP"), ("DOWN", 1, "TRIA_DOWN")):
            move = col.row(align=True)
            move.enabled = sm_edit.can_move(node, index, delta)
            move.operator(
                "redengine.sm_move_transition", text="", icon=icon
            ).direction = direction

        if not 0 <= index < len(records):
            return
        rec = records[index]
        shown = sm_edit.sections(rec)
        container = sm_edit.container_of(node)

        box = layout.box()
        box.label(
            text=f"{sm_edit.source_label(node)}  →  {sm_sockets.target_label(node, rec)}"
        )
        flags = box.row(align=True)
        if "enabled" in shown:
            flags.prop(rec, "enabled")
        if "forced_true" in shown:
            flags.prop(rec, "forced_true", text="Forced true")

        col = layout.column()
        if container is not None:
            col.prop_search(
                rec,
                "target_name",
                container,
                "red_sm_states",
                text="Target",
                item_search_property="label",
                icon="NODE",
            )
        else:
            col.label(text=f"Target: {sm_sockets.target_label(node, rec)}")
        if "priority" in shown:
            col.prop(rec, "priority")
        if "duration" in shown:
            col.prop(rec, "duration", text="Duration (s)")

        if "blend" in shown:
            _draw_blend(layout, rec)
        if "condition" in shown:
            _draw_condition(layout, rec)
        if "advanced" in shown:
            _draw_advanced(layout, rec)


class REDENGINE_UL_states(bpy.types.UIList):
    """The states of a state machine, in exported order"""

    bl_idname = "REDENGINE_UL_states"

    def filter_items(self, context, data, propname):
        read_models.refresh_state_rows(data)
        items = getattr(data, propname)
        flags = (
            bpy.types.UI_UL_list.filter_items_by_name(
                self.filter_name,
                self.bitflag_filter_item,
                items,
                "name",
                reverse=self.use_filter_invert,
            )
            if self.filter_name
            else []
        )
        order = (
            bpy.types.UI_UL_list.sort_items_by_name(items, "name")
            if self.use_filter_sort_alpha
            else []
        )
        return flags, order

    def draw_item(
        self, context, layout, data, item, icon, active_data, active_propname, index=0
    ):
        rows = read_models.state_rows(data)
        if not 0 <= index < len(rows):
            rows = read_models.refresh_state_rows(data)
        _handle, label, missing, is_default = rows[index]
        if missing:
            layout.label(text=f"{item.handle} (missing)", icon="ERROR")
            return
        layout.label(text=label, icon="HOME" if is_default else "NODE")


def _state_op(layout, idname: str, sm, **kwargs):
    op = layout.operator(idname, **kwargs)
    op.node_name = sm.name
    op.tree_name = sm.id_data.name
    return op


def _draw_import_notes(layout, sm):
    """Import findings kept on the state machine (e.g. a transition two states listed)"""
    notes = sm_edit.import_notes(sm)
    if not notes:
        return
    box = layout.box()
    head = box.row(align=True)
    head.label(text="Import notes", icon="INFO")
    _state_op(head, "redengine.sm_clear_import_notes", sm, text="", icon="X")
    col = box.column(align=True)
    for note in notes:
        col.label(text=note, icon="INFO")


class REDENGINE_PT_sm_states(bpy.types.Panel):
    bl_idname = "REDENGINE_PT_sm_states"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "Graph"
    bl_label = "States"

    @classmethod
    def poll(cls, context):
        space = getattr(context, "space_data", None)
        if space is None or getattr(space, "type", "") != "NODE_EDITOR":
            return False
        return context_state_machine(context) is not None

    def draw(self, context):
        layout = self.layout
        sm = context_state_machine(context)
        if sm is None:
            return
        row = layout.row()
        row.template_list(
            "REDENGINE_UL_states",
            "",
            sm,
            "red_sm_states",
            sm,
            "red_sm_states_index",
            rows=4,
        )
        refs = sm.red_sm_states
        index = sm.red_sm_states_index
        selected = sm_edit.state_for_ref(sm, index) is not None
        col = row.column(align=True)
        _state_op(col, "redengine.sm_add_state", sm, text="", icon="ADD")
        delete = col.row(align=True)
        delete.enabled = (
            0 <= index < len(refs)
        )  # a missing state's entry can be removed too
        _state_op(delete, "redengine.sm_delete_state", sm, text="", icon="REMOVE")
        col.separator()
        for direction, delta, icon in (("UP", -1, "TRIA_UP"), ("DOWN", 1, "TRIA_DOWN")):
            move = col.row(align=True)
            move.enabled = 0 <= index < len(refs) and 0 <= index + delta < len(refs)
            _state_op(
                move, "redengine.sm_move_state", sm, text="", icon=icon
            ).direction = direction
        col.separator()
        home = col.row(align=True)
        home.enabled = selected
        _state_op(home, "redengine.sm_set_default_state", sm, text="", icon="HOME")

        _draw_import_notes(layout, sm)

        entry = _pseudo_node(sm.node_tree, ENTRY_RED_TYPE)
        rec = sm_edit.default_row(entry)
        if rec is None:
            layout.label(text="This state machine has no Entry node", icon="ERROR")
            return
        layout.prop_search(
            rec,
            "target_name",
            sm,
            "red_sm_states",
            text="Default state",
            item_search_property="label",
            icon="HOME",
        )
        if not rec.target_handle:
            layout.label(text="Pick a default state before exporting", icon="ERROR")


STATE_MACHINE_UI_CLASSES = (
    REDENGINE_MT_sm_add_condition,
    REDENGINE_MT_sm_change_condition,
    REDENGINE_UL_states,
    REDENGINE_PT_sm_states,
    REDENGINE_UL_transitions,
    REDENGINE_PT_transition_editor,
)
