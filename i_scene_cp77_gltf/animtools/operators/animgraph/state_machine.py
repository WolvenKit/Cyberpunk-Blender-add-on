import bpy

from ....blender.animgraph import sm_edit
from ....blender.operator_results import finish_operator
from ....core.log import get_logger
from ....core.notifications import report
from ...services.animgraph import state_machine

_LOG = get_logger(__name__)


class REDENGINE_OT_sm_select_transition(bpy.types.Operator):
    """Select this transition"""

    bl_idname = "redengine.sm_select_transition"
    bl_label = "Select Transition"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    node_name: bpy.props.StringProperty(name="Node", options={"SKIP_SAVE"})
    tree_name: bpy.props.StringProperty(name="Tree", options={"SKIP_SAVE"})
    index: bpy.props.IntProperty(name="Index", default=-1, options={"SKIP_SAVE"})

    @classmethod
    def description(cls, context, properties):
        node = state_machine.find_node(
            context, properties.tree_name, properties.node_name
        )
        return state_machine.transition_description(node, properties.index)

    def execute(self, context):
        node = state_machine.find_node(context, self.tree_name, self.node_name)
        return finish_operator(self, state_machine.select_transition(node, self.index))


_TYPE_ITEMS = tuple(
    (short, sm_edit.condition_label(short), "")
    for _family, shorts in sm_edit.CONDITION_FAMILIES
    for short in shorts
)


class _StateMachineEdit:
    def run(self, function, *args):
        return finish_operator(self, state_machine.apply_edit(function, *args))


class _TransitionOperator(_StateMachineEdit):
    """Acts on node_name in tree_name, else the active node, and its active row"""

    bl_options = {"REGISTER", "UNDO"}

    node_name: bpy.props.StringProperty(name="Node", options={"SKIP_SAVE"})
    tree_name: bpy.props.StringProperty(name="Tree", options={"SKIP_SAVE"})

    @staticmethod
    def _owner(context, props):
        if props.node_name:
            node = state_machine.find_node(context, props.tree_name, props.node_name)
        else:
            node = getattr(context, "active_node", None)
        return node if sm_edit.is_transition_owner(node) else None

    @classmethod
    def poll(cls, context):
        return True

    def owner(self, context):
        node = self._owner(context, self)
        if node is None:
            report(
                self,
                "WARNING",
                "No state, Entry, Any State or state machine node",
                logger=_LOG,
            )
        return node

    def record(self, context):
        node = self.owner(context)
        if node is None:
            return None, None
        records = node.red_transitions
        index = node.red_transitions_index
        if not 0 <= index < len(records):
            report(self, "WARNING", "No transition selected", logger=_LOG)
            return node, None
        return node, records[index]


class REDENGINE_OT_sm_add_transition(_TransitionOperator, bpy.types.Operator):
    """Add a transition to this node (a conditional entry on Entry, a global transition on Any State)"""

    bl_idname = "redengine.sm_add_transition"
    bl_label = "Add Transition"

    def execute(self, context):
        node = self.owner(context)
        if node is None:
            return {"CANCELLED"}
        return self.run(sm_edit.add_transition, node, None)


class REDENGINE_OT_sm_delete_transition(_TransitionOperator, bpy.types.Operator):
    """Delete the selected transition"""

    bl_idname = "redengine.sm_delete_transition"
    bl_label = "Delete Transition"

    def execute(self, context):
        node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        return self.run(sm_edit.delete_transition, node, node.red_transitions_index)


class REDENGINE_OT_sm_move_transition(_TransitionOperator, bpy.types.Operator):
    """Move the selected transition up or down (row order is the export order)"""

    bl_idname = "redengine.sm_move_transition"
    bl_label = "Move Transition"

    direction: bpy.props.EnumProperty(
        name="Direction", items=(("UP", "Up", ""), ("DOWN", "Down", "")), default="UP"
    )

    def execute(self, context):
        node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        delta = -1 if self.direction == "UP" else 1
        return self.run(
            sm_edit.move_transition, node, node.red_transitions_index, delta
        )


class REDENGINE_OT_sm_add_condition(_TransitionOperator, bpy.types.Operator):
    """Add a condition to the selected transition"""

    bl_idname = "redengine.sm_add_condition"
    bl_label = "Add Condition"

    short: bpy.props.EnumProperty(name="Type", items=_TYPE_ITEMS)
    index: bpy.props.IntProperty(
        name="Group",
        default=-1,
        options={"SKIP_SAVE"},
        description="Condition (group) to add into; -1 for the root",
    )

    def execute(self, context):
        _node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        return self.run(sm_edit.add_condition, rec, self.short, self.index)


class REDENGINE_OT_sm_remove_condition(_TransitionOperator, bpy.types.Operator):
    """Remove this condition (and everything inside it)"""

    bl_idname = "redengine.sm_remove_condition"
    bl_label = "Remove Condition"

    index: bpy.props.IntProperty(name="Condition", default=0, options={"SKIP_SAVE"})

    def execute(self, context):
        _node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        return self.run(sm_edit.remove_condition, rec, self.index)


class REDENGINE_OT_sm_wrap_condition(_TransitionOperator, bpy.types.Operator):
    """Wrap this condition in an ALL-of group so more checks can be added beside it"""

    bl_idname = "redengine.sm_wrap_condition"
    bl_label = "Wrap in ALL of"

    index: bpy.props.IntProperty(name="Condition", default=0, options={"SKIP_SAVE"})

    def execute(self, context):
        _node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        return self.run(sm_edit.wrap_in_all, rec, self.index)


class REDENGINE_OT_sm_change_condition_type(_TransitionOperator, bpy.types.Operator):
    """Change this condition's type, carrying over fields with the same name"""

    bl_idname = "redengine.sm_change_condition_type"
    bl_label = "Change Condition Type"

    short: bpy.props.EnumProperty(name="Type", items=_TYPE_ITEMS)
    index: bpy.props.IntProperty(name="Condition", default=0, options={"SKIP_SAVE"})

    def execute(self, context):
        _node, rec = self.record(context)
        if rec is None:
            return {"CANCELLED"}
        return self.run(sm_edit.change_condition_type, rec, self.index, self.short)


class _StateMachineOperator(_StateMachineEdit):
    """Acts on the state machine node_name in tree_name, else the one in context"""

    bl_options = {"REGISTER", "UNDO"}

    node_name: bpy.props.StringProperty(name="Node", options={"SKIP_SAVE"})
    tree_name: bpy.props.StringProperty(name="Tree", options={"SKIP_SAVE"})

    def state_machine(self, context):
        sm = state_machine.editable_state_machine(
            context, self.tree_name, self.node_name
        )
        if sm is None:
            report(
                self, "WARNING", "No state machine with editable states", logger=_LOG
            )
        return sm

    def active_state(self, context):
        sm = self.state_machine(context)
        if sm is None:
            return None, None
        state = sm_edit.state_for_ref(sm, sm.red_sm_states_index)
        if state is None:
            report(self, "ERROR_INVALID_CONTEXT", "No state selected", logger=_LOG)
        return sm, state


class REDENGINE_OT_sm_add_state(_StateMachineOperator, bpy.types.Operator):
    """Add a new, empty state to this state machine"""

    bl_idname = "redengine.sm_add_state"
    bl_label = "Add State"

    def execute(self, context):
        sm = self.state_machine(context)
        if sm is None:
            return {"CANCELLED"}
        return self.run(sm_edit.add_state, sm)


class REDENGINE_OT_sm_delete_state(_StateMachineOperator, bpy.types.Operator):
    """Delete the selected state and its transitions"""

    bl_idname = "redengine.sm_delete_state"
    bl_label = "Delete State"

    def invoke(self, context, event):
        sm = self.state_machine(context)
        if sm is None:
            return {"CANCELLED"}
        index = sm.red_sm_states_index
        state = sm_edit.state_for_ref(sm, index)
        if state is not None:
            message = state_machine.delete_state_message(sm, state)
        elif sm_edit.missing_state_handle(sm, index):
            message = state_machine.missing_state_message(sm, index)
        else:
            report(self, "ERROR_INVALID_CONTEXT", "No state selected", logger=_LOG)
            return {"CANCELLED"}
        return context.window_manager.invoke_confirm(
            self,
            event,
            title="Delete State",
            message=message,
            confirm_text="Delete",
            icon="WARNING",
        )

    def execute(self, context):
        sm = self.state_machine(context)
        if sm is None:
            return {"CANCELLED"}
        return finish_operator(self, state_machine.delete_selected_state(sm))


class REDENGINE_OT_sm_move_state(_StateMachineOperator, bpy.types.Operator):
    """Move the selected state up or down (the order is the exported states order)"""

    bl_idname = "redengine.sm_move_state"
    bl_label = "Move State"

    direction: bpy.props.EnumProperty(
        name="Direction", items=(("UP", "Up", ""), ("DOWN", "Down", "")), default="UP"
    )

    def execute(self, context):
        sm = self.state_machine(context)
        if sm is None:
            return {"CANCELLED"}
        delta = -1 if self.direction == "UP" else 1
        return self.run(sm_edit.move_state, sm, sm.red_sm_states_index, delta)


class REDENGINE_OT_sm_clear_import_notes(_StateMachineOperator, bpy.types.Operator):
    """Dismiss these import notes (the Graph Validator stops warning about them)"""

    bl_idname = "redengine.sm_clear_import_notes"
    bl_label = "Dismiss Import Notes"

    def execute(self, context):
        sm = self.state_machine(context)
        if sm is None:
            return {"CANCELLED"}
        return self.run(sm_edit.clear_import_notes, sm)


class REDENGINE_OT_sm_set_default_state(_StateMachineOperator, bpy.types.Operator):
    """Make the selected state the default state (where the state machine starts)"""

    bl_idname = "redengine.sm_set_default_state"
    bl_label = "Set Default State"

    def execute(self, context):
        sm, state = self.active_state(context)
        if state is None:
            return {"CANCELLED"}
        return self.run(sm_edit.set_default_state, sm, state)


STATE_MACHINE_CLASSES = (
    REDENGINE_OT_sm_select_transition,
    REDENGINE_OT_sm_add_transition,
    REDENGINE_OT_sm_delete_transition,
    REDENGINE_OT_sm_move_transition,
    REDENGINE_OT_sm_add_condition,
    REDENGINE_OT_sm_remove_condition,
    REDENGINE_OT_sm_wrap_condition,
    REDENGINE_OT_sm_change_condition_type,
    REDENGINE_OT_sm_add_state,
    REDENGINE_OT_sm_delete_state,
    REDENGINE_OT_sm_move_state,
    REDENGINE_OT_sm_set_default_state,
    REDENGINE_OT_sm_clear_import_notes,
)
