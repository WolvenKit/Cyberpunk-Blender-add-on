import base64
import json
import zlib

RIG_EXPORT_TEMPLATE_KEY = "cp77_rig_export_template_zlib_b64"
RIG_EXPORT_TEMPLATE_VERSION = 1
RIG_IMPORT_MATRIX_KEY = "cp77_rig_import_matrix"
RIG_IMPORT_SOURCE_MODEL_KEY = "cp77_rig_import_source_model_matrix"
RIG_IMPORT_MATRIX_VERSION = 2


def encode_rig_export_template(document: dict) -> str:
    raw = json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(zlib.compress(raw, 9)).decode("ascii")


def decode_rig_export_template(payload: str) -> dict | None:
    if not payload:
        return None
    try:
        raw = zlib.decompress(base64.b64decode(payload.encode("ascii")))
        decoded = json.loads(raw.decode("utf-8"))
    except (ValueError, TypeError, zlib.error, json.JSONDecodeError):
        return None
    return decoded if isinstance(decoded, dict) else None
