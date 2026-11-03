import copy
import threading
from collections import OrderedDict
from dataclasses import dataclass


<<<<<<< Updated upstream
=======
def store_bounded(cache, key, value, *, limit=64):
    limit = max(0, int(limit))
    cache[key] = value
    while len(cache) > limit:
        cache.pop(next(iter(cache)))
    return value


def store_bounded_lru(cache, key, value, *, limit=64):
    limit = max(0, int(limit))
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > limit:
        cache.popitem(last=False)
    return value


>>>>>>> Stashed changes
@dataclass(frozen=True, slots=True)
class CachedDocument:
    payload: object
    validation: object
    resource_kind: object
    source_format: str


class DocumentCache:
    def __init__(self, limit=512):
        self.limit = max(0, int(limit))
        self._entries = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {"hits": 0, "misses": 0, "stores": 0, "evictions": 0}

    def get(self, key):
        with self._lock:
            value = self._entries.get(key)
            if value is None:
                self._stats["misses"] += 1
                return None
            self._entries.move_to_end(key)
            self._stats["hits"] += 1
            return CachedDocument(
                copy.deepcopy(value.payload),
                value.validation,
                value.resource_kind,
                value.source_format,
            )

<<<<<<< Updated upstream
=======
    def contains(self, key):
        with self._lock:
            return key in self._entries

>>>>>>> Stashed changes
    def store(self, key, value):
        if self.limit <= 0:
            return
        with self._lock:
            self._entries[key] = CachedDocument(
                copy.deepcopy(value.payload),
                value.validation,
                value.resource_kind,
                value.source_format,
            )
            self._entries.move_to_end(key)
            self._stats["stores"] += 1
            while len(self._entries) > self.limit:
                self._entries.popitem(last=False)
                self._stats["evictions"] += 1

    def clear(self):
        with self._lock:
            self._entries.clear()
            for key in self._stats:
                self._stats[key] = 0

    def stats(self):
        with self._lock:
            return {**self._stats, "entries": len(self._entries), "limit": self.limit}


PROCESS_DOCUMENT_CACHE = DocumentCache(512)
