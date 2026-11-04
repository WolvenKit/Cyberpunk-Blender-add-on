from __future__ import annotations

import math


def rig_float_value(rig_values, name):
    if rig_values is None or name not in rig_values:
        return None
    value = rig_values[name]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"Rig float track {name!r} is not finite")
    return value


def resolve_float_variable(name, declarations, rig_values=None, *, undeclared=None):
    """A float variable's value"""
    value = rig_float_value(rig_values, name)
    if value is not None:
        return value
    for variable in declarations or ():
        if str(getattr(variable, "name", "") or "") != name:
            continue
        if str(getattr(variable, "var_type", "") or "") != "Float":
            if undeclared is not None:
                return float(undeclared)
            raise ValueError(f"AnimGraph variable {name!r} is not a Float")
        return float(getattr(variable, "current_float", 0.0))
    if undeclared is not None:
        return float(undeclared)
    raise ValueError(f"AnimGraph float variable {name!r} is not declared")
