import json

from ....blender.animgraph import presenters, sm_edit, variables
from ....blender.animgraph.property_ui import draw_property_row
from ....core.log import get_logger, log_once
from .variable_widgets import draw_variable_value

_LOG = get_logger(__name__)


def _draw_variable_binding_box(owner, layout):
    red_type = getattr(owner, "red_type", "")
    if not red_type.startswith("animAnimNode_") or not red_type.endswith("Variable"):
        return
    supported = (
        "FloatVariable",
        "IntVariable",
        "BoolVariable",
        "VectorVariable",
        "QuaternionVariable",
        "TransformVariable",
    )
    if not red_type.endswith(supported):
        return
    binding = variables.bound_float_property(owner)
    if binding is not None:
        armature, name = binding
        box = layout.box()
        box.label(text=f"{name} — Rig Float Track", icon="LINKED")
        box.prop(armature, f"[{json.dumps(name)}]", text="Value")
        return
    variable = variables.variable_declaration(owner)
    if variable is None:
        try:
            name = variables.node_variable_name(owner)
        except (
            AttributeError,
            ReferenceError,
            RuntimeError,
            TypeError,
            ValueError,
        ) as error:
            log_once(
                _LOG,
                "DEBUG",
                ("_draw_variable_binding_box", type(error).__name__),
                "draw variable binding box: fell back after %s",
                error,
                exc_info=True,
            )
            name = ""
        box = layout.box()
        box.label(text=name or "Variable", icon="UNLINKED")
        box.label(text="Variable not declared in the graph", icon="INFO")
        return
    box = layout.box()
    box.label(text=str(getattr(variable, "name", "") or "Variable"), icon="LINKED")
    draw_variable_value(box, variable)


def draw_node(node, context, layout):
    presenter_id = presenters.node_presenter_id(node)
    if presenter_id == presenters.PRESENTER_VARIABLE_READER:
        _draw_variable_binding_box(node, layout)
    column = layout.column(align=True)

    editor_names = []
    for suffix in ("a", "b"):
        tree_name = getattr(node, f"red_editor_subgraph_{suffix}_name", "")
        label = getattr(node, f"red_editor_subgraph_{suffix}_label", "")
        if tree_name:
            editor_names.append((tree_name, label or tree_name))
    if editor_names:
        box = column.box()
        box.label(text="Editor Subgraphs", icon="NODETREE")
        for tree_name, label in editor_names:
            operator = box.operator(
                "redengine.enter_editor_subgraph", text=label, icon="NODETREE"
            )
            operator.tree_name = tree_name

    hidden = sm_edit.hidden_property_keys(node)
    shown = [
        (index, item)
        for index, item in enumerate(getattr(node, "red_properties", None) or ())
        if item.key not in hidden
    ]
    if not shown:
        column.label(text="No editable properties.", icon="INFO")
        return
    box = column.box()
    box.label(text="REDengine Properties", icon="PROPERTIES")
    for index, item in shown:
        draw_property_row(node, box, item, index)
