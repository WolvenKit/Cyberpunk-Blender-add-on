def draw_variable_value(layout, variable):
    """Current and default value controls for one AnimGraph variable declaration"""
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
        has_range = bool(getattr(variable, "has_float_range", False))
        row = layout.row(align=True)
        row.prop(variable, "current_float", text="Value")
        row.prop(variable, "default_float", text="Default")
        if has_range:
            row = layout.row(align=True)
            row.label(text="Range")
            row.prop(variable, "min_float", text="Min")
            row.prop(variable, "max_float", text="Max")
    elif variable_type in {"Vector", "Quaternion"}:
        labels = (
            ("i", "j", "k", "r")
            if variable_type == "Quaternion"
            else ("X", "Y", "Z", "W")
        )
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
