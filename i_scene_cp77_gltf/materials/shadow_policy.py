def object_shadow_policy(no_shadow_flags):
    flags = tuple(bool(flag) for flag in no_shadow_flags)
    if not flags:
        return True, False
    if all(flags):
        return False, False
    return True, any(flags)
