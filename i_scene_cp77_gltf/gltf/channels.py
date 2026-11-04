from __future__ import annotations


def named_channel(name: str, base_name: str, semantic: str) -> int | None:
    if name == base_name:
        return 0
    for prefix in (base_name + "_", semantic + "_"):
        if name.startswith(prefix) and name[len(prefix) :].isdigit():
            return int(name[len(prefix) :])
    return None


def assign_attribute_channels(
    layer_names, *, base_name: str, semantic: str, max_channels: int
):
    """Reserve named channels, then assign author-named layers to unused channels"""
    names = tuple(str(name) for name in layer_names)
    assigned = {}
    owners = {}
    for index, name in enumerate(names):
        channel = named_channel(name, base_name, semantic)
        if channel is None:
            continue
        if channel >= max_channels:
            raise ValueError(
                f"{name!r} requests unsupported {semantic}_{channel}; supported channels are 0 through {max_channels - 1}."
            )
        if channel in owners:
            raise ValueError(
                f"{names[owners[channel]]!r} and {name!r} both request {semantic}_{channel}; rename one layer explicitly."
            )
        assigned[index] = channel
        owners[channel] = index
    free = iter(channel for channel in range(max_channels) if channel not in owners)
    for index, name in enumerate(names):
        if index in assigned:
            continue
        channel = next(free, None)
        if channel is None:
            raise ValueError(
                f"No {semantic} channel remains for {name!r}; remove or reassign extra layers before export."
            )
        assigned[index] = channel
    return tuple(sorted(assigned.items(), key=lambda item: item[1]))
