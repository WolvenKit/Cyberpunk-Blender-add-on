from __future__ import annotations

import json
from dataclasses import asdict, dataclass

IMPORT_RECORD_KEY = "cp77_entity_import"


@dataclass(frozen=True, slots=True)
class ImportedAppearance:
    """What one import of an entity recorded on an appearance collection"""

    import_id: str
    ent_path: str
    app_path: str
    app_depot: str
    appearance: str
    entry_name: str
    collection_names: tuple[tuple[str, str], ...]


def encode_import_record(record: ImportedAppearance) -> str:
    return json.dumps(asdict(record), separators=(",", ":"), ensure_ascii=False)


def decode_import_record(text: str) -> ImportedAppearance:
    values = json.loads(text)
    values["collection_names"] = tuple(
        tuple(pair) for pair in values.get("collection_names", ())
    )
    return ImportedAppearance(**values)
