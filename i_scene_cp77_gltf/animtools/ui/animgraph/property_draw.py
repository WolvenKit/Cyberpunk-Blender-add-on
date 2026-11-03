from ....blender.animgraph import presenters, variables
from ....blender.animgraph.property_ui import draw_property_row


def _variable_decl_for_node(owner):
    try:
        root = variables.root_tree_for(getattr(owner, "id_data", None))
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        root = None
    if root is None:
        return None
    variable_type = variables.variable_type_for_node(owner)
    name = variables.node_variable_name(owner)
    for variable in getattr(root, "variables", ()):
        if (
            str(getattr(variable, "var_type", "")) == variable_type
            and str(getattr(variable, "name", "")) == name
        ):
            return variable
    return None


def _draw_variable_value_controls(layout, variable):
    variable_type = str(getattr(variable, "var_type", ""))
    if variable_type == "Bool":
        row = layout.row(align=True)
        row.prop(variable, "current_bool", text="Value")
        row.prop(variable, "default_bool", text="Default")
    elif variable_type == "Int":
        row = layout.row(align=True)
        row.prop(variable, "current_int", text="Value")
        row.prop(variable, "default_int", text="Default")
    elif variable_type == "Float":
        row = layout.row(align=True)
        row.prop(variable, "current_float", text="Value")
        row.prop(variable, "default_float", text="Default")
        if bool(getattr(variable, "has_float_range", False)):
            row = layout.row(align=True)
            row.label(text="Range")
            row.prop(variable, "min_float", text="Min")
            row.prop(variable, "max_float", text="Max")
    elif variable_type in {"Vector", "Quaternion"}:
        labels = ("i", "j", "k", "r") if variable_type == "Quaternion" else ("X", "Y", "Z", "W")
        row = layout.row(align=True)
        row.label(text="Value")
        for index, label in enumerate(labels):
            row.prop(variable, "current_vector", index=index, text=label)
        row = layout.row(align=True)
        row.label(text="Default")
        for index, label in enumerate(labels):
            row.prop(variable, "default_vector", index=index, text=label)
    else:
        layout.prop(variable, "current_value", text="Value")
        layout.prop(variable, "default_value", text="Default")


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
    variable = _variable_decl_for_node(owner)
    if variable is None:
        try:
            name = variables.node_variable_name(owner)
        except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
            name = ""
        box = layout.box()
        box.label(text=name or "Variable", icon="UNLINKED")
        box.label(text="No matching graph variable declaration.", icon="INFO")
        return
    box = layout.box()
    box.label(text=str(getattr(variable, "name", "") or "Variable"), icon="LINKED")
    _draw_variable_value_controls(box, variable)


def _draw_node_properties(owner, layout):
    presenter_id = presenters.node_presenter_id(owner)
    if presenter_id == presenters.PRESENTER_VARIABLE_READER:
        _draw_variable_binding_box(owner, layout)
    column = layout.column(align=True)
    column.label(text=f"ID {owner.red_handle_id}")
    if presenter_id and presenter_id != presenters.PRESENTER_GENERIC:
        column.label(
            text=f"Presenter: {presenters.presenter_info(presenter_id).label}",
            icon="PLUGIN",
        )
    if (
        getattr(owner, "red_pseudo", False)
        or getattr(owner, "red_parent_class", "")
        or getattr(owner, "red_output_kind", "")
    ):
        row = column.row(align=True)
        is_editor = getattr(owner, "red_pseudo", False)
        row.label(
            text="Editor" if is_editor else "Runtime",
            icon="GHOST_ENABLED" if is_editor else "NODE",
        )
        row.label(text=f"Out: {getattr(owner, 'red_output_kind', '') or 'sink/editor'}")

    editor_names = []
    for suffix in ("a", "b"):
        tree_name = getattr(owner, f"red_editor_subgraph_{suffix}_name", "")
        label = getattr(owner, f"red_editor_subgraph_{suffix}_label", "")
        if tree_name:
            editor_names.append((tree_name, label or tree_name))
    if editor_names:
        box = column.box()
        box.label(text="Editor Subgraphs", icon="NODETREE")
        for tree_name, label in editor_names:
            operator = box.operator("redengine.enter_editor_subgraph", text=label, icon="NODETREE")
            operator.tree_name = tree_name

    properties = getattr(owner, "red_properties", None)
    if not properties:
        column.label(text="No editable properties.", icon="INFO")
        return
    box = column.box()
    box.label(text="REDengine Properties", icon="PROPERTIES")
    for index, item in enumerate(properties):
        draw_property_row(owner, box, item, index)


def draw_node(node, context, layout):
    _draw_node_properties(node, layout)
