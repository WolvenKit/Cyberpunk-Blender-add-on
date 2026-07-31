import os
from dataclasses import dataclass

from .catalog import ResourceKind, resource_spec_for_path
from .diagnostics import IssueSeverity, ResourceIssue


def _cache_key(value):
    if isinstance(value, dict):
        return tuple(sorted((str(key), _cache_key(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_cache_key(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_cache_key(item) for item in value))
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


@dataclass(frozen=True, slots=True)
class RepositoryCacheKey:
    identity: tuple
    kind: str
    parser_revision: int
    options: tuple


class ResourceLoadError(RuntimeError):
    def __init__(self, source, resource_kind, issues):
        self.source = str(source or "")
        self.resource_kind = ResourceKind(resource_kind)
        self.issues = tuple(issues)
        message = self.issues[-1].message if self.issues else f"Failed to load {self.resource_kind.value}: {self.source}"
        super().__init__(message)


class ResourceRepository:
    def __init__(
        self,
        documents,
        *,
        resource_kind,
        parser,
        parser_revision=1,
        asset_index=None,
        export_suffix="",
        accepted_kinds=(),
        parser_receives_document=False,
    ):
        self.documents = documents
        self.resource_kind = ResourceKind(resource_kind)
        self.parser = parser
        self.parser_revision = int(parser_revision)
        self.asset_index = asset_index
        self.export_suffix = str(export_suffix or "")
        self.accepted_kinds = frozenset((self.resource_kind, *(ResourceKind(kind) for kind in accepted_kinds)))
        self.parser_receives_document = bool(parser_receives_document)
        self._cache = {}
        self._issues = []
        self._hits = 0
        self._misses = 0

    @property
    def issues(self):
        return tuple(self._issues)

    @property
    def stats(self):
        return {"hits": self._hits, "misses": self._misses, "entries": len(self._cache)}

    def clear(self):
        self._cache.clear()
        self._issues.clear()
        self._hits = 0
        self._misses = 0

    def resolve(self, reference):
        value = os.fspath(reference) if reference else ""
        if not value:
            return ""
        if os.path.isfile(value):
            return os.path.abspath(value)
        if self.asset_index is None or not self.export_suffix:
            return ""
        return self.asset_index.resolve_expected(value, self.export_suffix) or ""

    def load(self, reference, *, required=False, parser_options=None, parser_kwargs=None):
        source = self.resolve(reference)
        if not source:
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "repository.resolve",
                str(reference or ""),
                f"{reference}: resource could not be resolved",
                self.resource_kind.value,
            )
            self._issues.append(issue)
            if required:
                raise ResourceLoadError(reference, self.resource_kind, (issue,))
            return None

        spec = resource_spec_for_path(source)
        actual_kind = spec.kind if spec is not None and spec.kind in self.accepted_kinds else self.resource_kind
        issue_start = len(self.documents.issues)
        document = self.documents.load(
            source,
            expected_kind=actual_kind,
            allow_invalid=True,
        )
        if document is None:
            issues = self.documents.issues[issue_start:]
            self._issues.extend(issues)
            if required:
                raise ResourceLoadError(source, actual_kind, issues)
            return None
        if not document.validation.valid:
            issues = document.validation.issues
            self._issues.extend(issues)
            if required:
                raise ResourceLoadError(source, actual_kind, issues)
            return None

        options = _cache_key(parser_options or ())
        key = RepositoryCacheKey(
            document.identity.key,
            actual_kind.value,
            self.parser_revision,
            tuple(options) if isinstance(options, tuple) else (options,),
        )
        parsed = self._cache.get(key)
        if parsed is not None:
            self._hits += 1
            return parsed
        self._misses += 1

        kwargs = dict(parser_kwargs or {})
        try:
            parsed = self.parser(document if self.parser_receives_document else document.payload, **kwargs)
        except Exception as error:
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "repository.parse",
                source,
                f"{source}: {error}",
                actual_kind.value,
            )
            self._issues.append(issue)
            if required:
                raise ResourceLoadError(source, actual_kind, (issue,)) from error
            return None
        self._cache[key] = parsed
        return parsed
