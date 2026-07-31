from __future__ import annotations

from dataclasses import dataclass

from ...common.paths import (
    depot_path_key,
    expected_resource_path,
    normalize_depot_path,
)


@dataclass(slots=True, frozen=True)
class IndexedResourceResolution:
    kind: str
    depot_path: str
    resolved_path: str
    expected_path: str
    status: str


class IndexedResourceResolver:
    def __init__(self, session):
        self.session = session
        self.cache = session.caches.resource_resolutions

    def resolve(
        self,
        kind,
        depot_path,
        candidates,
        *,
        append_expected_json=True,
    ):
        normalized = normalize_depot_path(depot_path)
        normalized_candidates = tuple(
            (bool(append_json), str(extension))
            for append_json, extension in candidates
        )
        cache_key = (
            str(kind),
            depot_path_key(normalized),
            normalized_candidates,
            bool(append_expected_json),
        )
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        if not normalized:
            result = IndexedResourceResolution(
                kind=str(kind),
                depot_path="",
                resolved_path="",
                expected_path="",
                status="NO_RESOURCE_PATH",
            )
            self.cache[cache_key] = result
            return result

        resolved_path = ""
        for append_json, extension in normalized_candidates:
            indexed_path = normalized
            if append_json and not indexed_path.lower().endswith(".json"):
                indexed_path = f"{indexed_path}.json"
            resolved_path = (
                self.session.asset_index.resolve_expected(
                    indexed_path,
                    extension,
                )
                or ""
            )
            if resolved_path:
                break

        result = IndexedResourceResolution(
            kind=str(kind),
            depot_path=normalized,
            resolved_path=resolved_path,
            expected_path=expected_resource_path(
                self.session.raw_root,
                normalized,
                append_json=append_expected_json,
            ),
            status=("RESOLVED" if resolved_path else "RESOURCE_NOT_INDEXED"),
        )
        self.cache[cache_key] = result
        return result

    def resolve_json(self, kind, depot_path, expected_extension):
        return self.resolve(
            kind,
            depot_path,
            ((True, expected_extension),),
            append_expected_json=True,
        )
