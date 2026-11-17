import os

from ...assetio.cache import store_bounded
from ...assetio.documents import DocumentSession, FileIdentity
from ...core.log import debug_exception, get_logger
from .repository import EntityRepository

_LOG = get_logger(__name__)
_ENTITY_APPEARANCE_CACHE = {}
_ENTITY_APPEARANCE_CACHE_LIMIT = 32


def clear_entity_appearance_cache():
    _ENTITY_APPEARANCE_CACHE.clear()


def load_entity_for_dialog(filepath):
    if not filepath or not os.path.isfile(filepath):
        return None
    try:
        source_identity = FileIdentity.from_path(filepath)
    except OSError:
        debug_exception(_LOG, "Could not read %s; the dialog shows no entity", filepath)
        return None
    normalized = source_identity.path.key
    identity = (
        normalized,
        source_identity.mtime_ns,
        source_identity.size,
    )
    cached = _ENTITY_APPEARANCE_CACHE.get(identity)
    if cached is not None:
        return cached
    for key in tuple(_ENTITY_APPEARANCE_CACHE):
        if key[0] == normalized:
            _ENTITY_APPEARANCE_CACHE.pop(key, None)
    with DocumentSession() as documents:
        entity = EntityRepository(documents).load(filepath, required=True)
    return store_bounded(
        _ENTITY_APPEARANCE_CACHE,
        identity,
        entity,
        limit=_ENTITY_APPEARANCE_CACHE_LIMIT,
    )
