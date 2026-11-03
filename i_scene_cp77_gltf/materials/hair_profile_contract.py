import json

SAMPLE_COUNT_PROP = "cp77_hair_profile_sample_count"
_SOURCE_ENTRIES_PREFIX = "cp77_hair_profile_source_"


def source_entries_property(gradient_key):
    return _SOURCE_ENTRIES_PREFIX + str(gradient_key)


def encode_source_entries(entries):
    return json.dumps(list(entries or ()), separators=(",", ":"), ensure_ascii=False)


def decode_source_entries(value):
    if not value:
        return None
    try:
        decoded = json.loads(str(value))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, list) or not all(
        isinstance(entry, dict) for entry in decoded
    ):
        return None
    return decoded


def store_source_profile(material, profile):
    if not isinstance(profile, dict):
        return
    for gradient_key in ("gradientEntriesID", "gradientEntriesRootToTip"):
        entries = profile.get(gradient_key)
        if isinstance(entries, list):
            material[source_entries_property(gradient_key)] = encode_source_entries(
                entries
            )
    sample_count = profile.get("sampleCount")
    if isinstance(sample_count, (int, float)) and int(sample_count) > 0:
        material[SAMPLE_COUNT_PROP] = int(sample_count)
