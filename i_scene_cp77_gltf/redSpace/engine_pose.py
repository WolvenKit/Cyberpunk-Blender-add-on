from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping

from ..bartmoss.qs_transform import QsTransform
from .transforms import current_bone_trs_to_red, red_trs_to_current_bone


def frame_value_to_engine(
    value: QsTransform, *, relative_to_parent: bool
) -> QsTransform:
    """An imported-rig transform as the engine transform"""
    return QsTransform(
        *current_bone_trs_to_red(
            value.translation,
            value.rotation_xyzw,
            value.scale,
            relative_to_parent=relative_to_parent,
        )
    )


def engine_value_to_frame(
    value: QsTransform, *, relative_to_parent: bool
) -> QsTransform:
    """An engine transform as the imported rig's transform"""
    return QsTransform(
        *red_trs_to_current_bone(
            value.translation,
            value.rotation_xyzw,
            value.scale,
            relative_to_parent=relative_to_parent,
        )
    )


def relative_to_parent(
    name: str,
    parent_map: Mapping[str, str],
    frame: Mapping[str, QsTransform],
    model_space: bool,
) -> bool:
    # A frame root (or any model-space value) is relative to the armature, not to a parent bone.
    parent = str(parent_map.get(name, "") or "")
    return not model_space and bool(parent) and parent in frame


class EngineSpacePose(MutableMapping):
    def __init__(
        self,
        frame_pose: MutableMapping[str, QsTransform],
        parent_map: Mapping[str, str],
        *,
        model_space: bool = False,
    ):
        self._frame = frame_pose
        self._parents = parent_map
        self._model_space = bool(model_space)
        self._cache: dict[str, QsTransform] = {}
        self.written: set[str] = set()

    def __getitem__(self, name: str) -> QsTransform:
        cached = self._cache.get(name)
        if cached is None:
            # Parents created through this view (stack transforms) count as present.
            relative = relative_to_parent(name, self._parents, self, self._model_space)
            cached = self._cache[name] = frame_value_to_engine(
                self._frame[name], relative_to_parent=relative
            )
        return cached

    def __setitem__(self, name: str, value: QsTransform) -> None:
        self._cache[name] = value
        self.written.add(name)

    def __delitem__(self, name: str) -> None:
        raise TypeError("EngineSpacePose does not remove transforms")

    def __contains__(self, name: object) -> bool:
        return name in self._cache or name in self._frame

    def __iter__(self) -> Iterator[str]:
        return iter(self._frame)

    def __len__(self) -> int:
        return len(self._frame)

    def commit(self) -> None:
        for name in self.written:
            relative = relative_to_parent(name, self._parents, self, self._model_space)
            self._frame[name] = engine_value_to_frame(
                self._cache[name], relative_to_parent=relative
            )
        self.written.clear()
