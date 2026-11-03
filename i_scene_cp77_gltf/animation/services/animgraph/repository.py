from __future__ import annotations

import os

from ....assetio import animgraph_json
from ....assetio.files import read_bytes
from ....assetio.paths import is_local_absolute
from ...model.animgraph.document import AnimGraphDocument

ANIMGRAPH_EXPORT_SUFFIX = ".animgraph.json"


class AnimGraphRepository:
    """Reads AnimGraph exports with assetio.animgraph_json"""

    def __init__(self, *, asset_index=None):
        self.asset_index = asset_index

    def resolve(self, reference) -> str:
        """A local path as given, or a depot path through the asset index"""
        value = os.fspath(reference) if reference else ""
        if not value or is_local_absolute(value) or self.asset_index is None:
            return value
        return self.asset_index.resolve_expected(value, ANIMGRAPH_EXPORT_SUFFIX) or ""

    def load(self, reference) -> AnimGraphDocument:
        path = self.resolve(reference)
        if not path:
            raise FileNotFoundError(
                f"AnimGraph export could not be resolved: {reference}"
            )
        source_text = read_bytes(path).decode("utf-8-sig")
        payload = animgraph_json.loads(source_text)
        if not isinstance(payload, dict):
            raise ValueError("AnimGraph JSON root must be an object")
        return AnimGraphDocument(path, payload, source_text)
