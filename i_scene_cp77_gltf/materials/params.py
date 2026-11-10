from collections import OrderedDict

from ..assetio.cache import store_bounded_lru

_PARAM_KEY_CACHE = OrderedDict()
_PARAM_KEY_CACHE_LIMIT = 4096
_PARAM_CACHE_STATS = {"hits": 0, "misses": 0}


def _normalized_param_keys(data, *, refresh=False):
    cache_key = id(data)
    cached = _PARAM_KEY_CACHE.get(cache_key)
    if (
        not refresh
        and cached is not None
        and cached[0] is data
        and cached[1] == len(data)
    ):
        _PARAM_KEY_CACHE.move_to_end(cache_key)
        _PARAM_CACHE_STATS["hits"] += 1
        return cached[2]

    _PARAM_CACHE_STATS["misses"] += 1
    normalized = {str(candidate).casefold(): candidate for candidate in data}
    store_bounded_lru(
        _PARAM_KEY_CACHE,
        cache_key,
        (data, len(data), normalized),
        limit=_PARAM_KEY_CACHE_LIMIT,
    )
    return normalized


def clear_param_key_cache():
    _PARAM_KEY_CACHE.clear()
    _PARAM_CACHE_STATS.update(hits=0, misses=0)


def param_key_cache_stats():
    return {**_PARAM_CACHE_STATS, "entries": len(_PARAM_KEY_CACHE)}


def lookup_param(data, key, default=None):
    if not isinstance(data, dict):
        return default
    if key in data:
        return data[key]
    normalized_key = str(key).casefold()
    matched = _normalized_param_keys(data).get(normalized_key)
    if matched is not None and matched not in data:
        matched = _normalized_param_keys(data, refresh=True).get(normalized_key)
    return data.get(matched, default) if matched is not None else default


def coerce_texture_path(value):
    visited = set()
    while isinstance(value, dict) and id(value) not in visited:
        visited.add(id(value))
        if "DepotPath" in value:
            value = value["DepotPath"]
        elif "$value" in value:
            value = value["$value"]
        elif "texture" in value:
            value = value["texture"]
        elif "value" in value:
            value = value["value"]
        else:
            return ""
    if not isinstance(value, str) or value == "null":
        return ""
    return value
