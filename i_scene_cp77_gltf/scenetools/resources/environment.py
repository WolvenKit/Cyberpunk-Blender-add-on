from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ...assetio.files import read_bytes

MASTER_KEY = "_master"


class _CurveData(dict):
    __slots__ = ("times",)

    def __init__(self, values):
        super().__init__(values)
        points = self.get("p", ())
        self.times = tuple(point[0] for point in points)


_DATA_PATH = (
    Path(__file__).resolve().parents[2]
    / "resources"
    / "scenetools"
    / "environment.json"
)


def _freeze(value):
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        frozen = {key: _freeze(item) for key, item in value.items()}
        if "p" in frozen and isinstance(frozen["p"], tuple):
            return _CurveData(frozen)
        return frozen
    return value


@lru_cache(maxsize=1)
def _environment_data():
    payload = json.loads(read_bytes(_DATA_PATH).decode("utf-8"))
    return (
        _freeze(payload.get("environmentBlocks", {})),
        _freeze(payload.get("weatherStateMeta", {})),
        _freeze(payload.get("weatherTransitions", ())),
    )


@lru_cache(maxsize=256)
def layered_block(block_type: str, weather: str | None = None):
    environment_blocks, _, _ = _environment_data()
    merged = dict(environment_blocks.get(MASTER_KEY, {}).get(block_type, {}))
    if weather and weather in environment_blocks:
        merged.update(environment_blocks[weather].get(block_type, {}))
    return merged


def weather_state_meta(weather: str | None):
    if not weather:
        return {}
    _, state_meta, _ = _environment_data()
    return dict(state_meta.get(weather, {}))
