import base64
import json
import zlib

from ....assetio.paths import local_path_key

RIG_EXPORT_TEMPLATE_KEY = "cp77_rig_export_template_zlib_b64"
RIG_IMPORT_MATRIX_KEY = "cp77_rig_import_matrix"
RIG_IMPORT_SOURCE_MODEL_KEY = "cp77_rig_import_source_model_matrix"
# A bundled MetaRig's part documents, by part path, for tools that read a part's rig.
RIG_PART_DOCUMENTS_KEY = "cp77_metarig_part_documents_zlib_b64"


def encode_json_document(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def _decode_json(payload):
    if not payload:
        return None
    try:
        raw = zlib.decompress(base64.b64decode(payload.encode("ascii")))
        return json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, zlib.error, json.JSONDecodeError):
        return None


def decode_rig_export_template(payload: str) -> dict | None:
    decoded = _decode_json(payload)
    return decoded if isinstance(decoded, dict) else None


def decode_rig_part_documents(payload) -> dict:
    decoded = _decode_json(str(payload or ""))
    if not isinstance(decoded, dict):
        return {}
    return {
        str(path): document
        for path, document in decoded.items()
        if isinstance(document, dict)
    }


def source_rig_paths_from(
    ledger_payload, merge_order, legacy_values
) -> tuple[str, ...]:
    """Active source rig paths"""
    candidates = []
    try:
        ledger = json.loads(str(ledger_payload))
    except (TypeError, ValueError):
        ledger = []
    if isinstance(ledger, list):
        candidates.extend(
            entry.get("path", "") for entry in ledger if isinstance(entry, dict)
        )
    if not candidates:
        candidates.extend(merge_order or ())
    if not candidates:
        for value in legacy_values:
            if value.startswith("metarig:") or ";" in value:
                candidates.extend(value.removeprefix("metarig:").split(";"))
            else:
                candidates.append(value)
    unique = {}
    for value in candidates:
        path = str(value or "")
        if path.casefold().endswith(".rig.json"):
            unique.setdefault(local_path_key(path), path)
    return tuple(unique.values())


def decode_rig_part_bindings(payload) -> tuple[dict[str, str], ...]:
    try:
        values = json.loads(str(payload or "[]"))
    except (TypeError, ValueError, json.JSONDecodeError):
        values = []
    if not isinstance(values, list):
        return ()
    result = []
    for value in values:
        if not isinstance(value, dict):
            continue
        path = str(value.get("path", "") or "")
        source_path = str(value.get("source_path", "") or "")
        component = str(value.get("component", "") or "")
        graph = str(value.get("graph", "") or "")
        if not path and not source_path:
            continue
        result.append(
            {
                "path": path,
                "source_path": source_path,
                "component": component,
                "graph": graph,
            }
        )
    return tuple(result)
