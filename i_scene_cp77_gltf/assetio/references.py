def resource_references(payload, suffix):
    pending = [payload]
    seen = set()
    suffix = suffix.casefold()
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            pending.extend(reversed(tuple(value.values())))
        elif isinstance(value, (list, tuple)):
            pending.extend(reversed(value))
        elif isinstance(value, str) and value.casefold().endswith(
            (suffix, suffix + ".json")
        ):
            if value not in seen:
                seen.add(value)
                yield value
