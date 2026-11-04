from __future__ import annotations


def _leaf(path: str) -> str:
    return str(path or "").replace("/", "\\").casefold().rsplit("\\", 1)[-1]


def match_action_source_rig(rigs, bone_names, rig_path, action_name: str):
    """Pick the source rig an additive Action was authored against"""
    action_names = tuple(str(name) for name in bone_names)
    if action_names:
        for rig in rigs:
            if tuple(str(name) for name in rig.bone_names) == action_names:
                return rig

    rig_leaf = _leaf(rig_path).removesuffix(".rig") if rig_path else ""
    if rig_leaf:
        for rig in rigs:
            source_leaf = (
                _leaf(getattr(rig, "source_path", ""))
                .removesuffix(".json")
                .removesuffix(".rig")
            )
            if source_leaf == rig_leaf:
                return rig

    if action_names:
        action_set = set(action_names)
        scored = sorted(
            (
                (
                    len(action_set.intersection(map(str, rig.bone_names))),
                    -abs(len(rig.bone_names) - len(action_names)),
                    rig,
                )
                for rig in rigs
            ),
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
        if scored and scored[0][0] > 0:
            return scored[0][2]
    if len(rigs) == 1:
        return rigs[0]
    raise ValueError(
        f"Could not match additive Action '{action_name}' to a source rig."
    )
