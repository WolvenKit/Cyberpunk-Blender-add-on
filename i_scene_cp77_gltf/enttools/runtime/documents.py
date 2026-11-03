from __future__ import annotations

import os

from ...assetio.documents import file_identity, load_json_payload
from ...entity.domain.document import AppearanceDocument, EntityDocument

_CACHE: dict = {}


def source_documents(
    app_path: str, ent_path: str
) -> tuple[AppearanceDocument, EntityDocument]:
    """The appearance and entity documents"""
    for path in (app_path, ent_path):
        if not os.path.isfile(path):
            raise FileNotFoundError(
                f"{path} is missing; it was moved or deleted after import"
            )
    key = (file_identity(app_path), file_identity(ent_path))
    cached = _CACHE.get((app_path, ent_path))
    if cached is not None and cached[0] == key:
        return cached[1]
    documents = (
        AppearanceDocument(load_json_payload(app_path)),
        EntityDocument(load_json_payload(ent_path)),
    )
    _CACHE[(app_path, ent_path)] = (key, documents)
    return documents


def clear_source_documents() -> None:
    _CACHE.clear()
