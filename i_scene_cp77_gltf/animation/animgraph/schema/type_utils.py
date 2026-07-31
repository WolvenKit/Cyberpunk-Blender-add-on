def unwrap_indirect_type(type_name: str) -> str:
    value = str(type_name or '').strip()
    while True:
        if value.startswith('handle:'):
            value = value[len('handle:'):]
            continue
        if value.startswith('whandle:'):
            value = value[len('whandle:'):]
            continue
        if value.startswith('raRef:'):
            value = value[len('raRef:'):]
            continue
        if value.startswith('array:'):
            value = value[len('array:'):]
            continue
        return value
