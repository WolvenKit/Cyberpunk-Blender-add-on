def plain_value(value):
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict) or hasattr(value, "keys"):
        return {str(key): plain_value(value[key]) for key in value.keys()}
    try:
        return [plain_value(item) for item in value]
    except TypeError:
        return str(value)
