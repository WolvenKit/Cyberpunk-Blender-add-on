from __future__ import annotations

from collections import Counter

from .values import cname_text


def rig_array_errors(root) -> tuple[str, ...]:
    """Validate rig parallel arrays and hierarchy without mutating the payload."""

    if not isinstance(root, dict):
        return ("rig root must be an object",)

    names = root.get("boneNames")
    parents = root.get("boneParentIndexes")
    transforms = root.get("boneTransforms")
    if not isinstance(names, list):
        return ("boneNames must be a list",)
    if not isinstance(parents, list):
        return ("boneParentIndexes must be a list",)
    if not isinstance(transforms, list):
        return ("boneTransforms must be a list",)

    count = len(names)
    errors = []
    if len(parents) != count:
        errors.append(
            f"boneParentIndexes count {len(parents)} does not match "
            f"boneNames count {count}"
        )
    if len(transforms) != count:
        errors.append(
            f"boneTransforms count {len(transforms)} does not match "
            f"boneNames count {count}"
        )
    for field in ("aPoseLS", "aPoseMS"):
        values = root.get(field)
        if values is not None and not isinstance(values, list):
            errors.append(f"{field} must be a list when present")
        elif isinstance(values, list) and values and len(values) != count:
            errors.append(
                f"{field} count {len(values)} does not match boneNames count {count}"
            )

    decoded_names = [cname_text(value).strip() for value in names]
    empty_indices = [index for index, name in enumerate(decoded_names) if not name]
    if empty_indices:
        errors.append(
            "boneNames contains empty names at indices "
            + ", ".join(map(str, empty_indices[:16]))
        )
    name_counts = Counter(name for name in decoded_names if name)
    duplicates = sorted(name for name, total in name_counts.items() if total > 1)
    if duplicates:
        errors.append(
            "boneNames contains duplicate names: " + ", ".join(duplicates[:16])
        )

    if len(parents) == count:
        normalized = []
        for index, value in enumerate(parents):
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(
                    f"boneParentIndexes[{index}] must be an integer"
                )
                normalized.append(-1)
                continue
            parent = int(value)
            normalized.append(parent)
            if parent < -1 or parent >= count:
                errors.append(
                    f"boneParentIndexes[{index}]={parent} is outside "
                    f"[-1, {count - 1}]"
                )
            elif parent == index:
                errors.append(f"boneParentIndexes[{index}] references itself")

        state = [0] * count
        for start in range(count):
            if state[start] == 2:
                continue
            path = []
            position = {}
            current = start
            while 0 <= current < count and state[current] != 2:
                if current in position:
                    cycle = path[position[current]:] + [current]
                    errors.append(
                        "bone hierarchy contains a cycle: "
                        + " -> ".join(map(str, cycle))
                    )
                    break
                position[current] = len(path)
                path.append(current)
                parent = normalized[current]
                if parent < 0 or parent >= count:
                    break
                current = parent
            for index in path:
                state[index] = 2

    return tuple(dict.fromkeys(errors))
