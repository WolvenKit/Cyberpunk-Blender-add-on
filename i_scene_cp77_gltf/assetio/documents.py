import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..core.log import debug_exception, get_logger
from .cache import PROCESS_DOCUMENT_CACHE, CachedDocument
from .catalog import (
    CachePolicy,
    ResourceFormat,
    ResourceKind,
    resource_export_for_suffix,
    resource_spec_for_path,
)
from .diagnostics import IssueSeverity, ResourceIssue, ValidationResult
from .files import read_bytes, warm_file
from .paths import LocalPath
from .resolver import full_suffix
from .validation import ValidationProfile, validate_payload

_LOG = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class FileIdentity:
    path: LocalPath
    mtime_ns: int
    size: int

    @classmethod
    def from_path(cls, path):
        local = LocalPath.from_value(path)
        stat_result = os.stat(local.value)
        mtime_ns = getattr(
            stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000)
        )
        return cls(local, int(mtime_ns), int(stat_result.st_size))

    @property
    def key(self):
        return self.path.key, self.mtime_ns, self.size


@dataclass(frozen=True, slots=True)
class PrefetchedSource:
    identity: FileIdentity
    data: bytes | None


@dataclass(frozen=True, slots=True)
class JsonDocument:
    source: LocalPath
    identity: FileIdentity
    payload: object
    resource_kind: ResourceKind | None
    source_format: str
    validation: ValidationResult


class DocumentLoadError(RuntimeError):
    def __init__(self, issue):
        super().__init__(issue.message)
        self.issue = issue


def _decode_json_bytes(data, path, constants=None):
    """The JSON payload of data"""

    def record_constant(name):
        if constants is not None:
            constants[name] = constants.get(name, 0) + 1
        return float(name)

    try:
        return json.loads(data.decode("utf-8-sig"), parse_constant=record_constant)
    except UnicodeDecodeError as error:
        raise DocumentLoadError(
            ResourceIssue(
                IssueSeverity.ERROR,
                "json.encoding",
                path,
                f"{path}: invalid UTF-8 at byte {error.start}",
            )
        ) from error
    except json.JSONDecodeError as error:
        signature = data[:16]
        if not signature:
            detail = "file is empty"
        elif signature[:4] == b"PK\x03\x04":
            detail = "file is a zip archive, not JSON"
        else:
            detail = f"starts with {signature!r}"
        raise DocumentLoadError(
            ResourceIssue(
                IssueSeverity.ERROR,
                "json.decode",
                path,
                f"{path}: {error.msg} at line {error.lineno}, column {error.colno} ({detail})",
            )
        ) from error


def _read_json_source(path):
    try:
        return read_bytes(path)
    except OSError as error:
        raise DocumentLoadError(
            ResourceIssue(
                IssueSeverity.ERROR,
                "file.read",
                path,
                f"{path}: {error}",
            )
        ) from error


def _source_contract(path, expected_kind):
    spec = resource_spec_for_path(path)
    kind = (
        ResourceKind(expected_kind)
        if expected_kind is not None
        else (spec.kind if spec is not None else None)
    )
    suffix = full_suffix(path)
    export = resource_export_for_suffix(suffix)
    source_format = (
        export[1].format.value if export is not None else ResourceFormat.JSON.value
    )
    profile = (
        ValidationProfile(spec.validation_profile)
        if spec is not None
        else ValidationProfile.NONE
    )
    cache_policy = spec.cache_policy if spec is not None else CachePolicy.SESSION
    expected_root_types = spec.expected_root_types if spec is not None else ()
    return spec, kind, source_format, profile, cache_policy, expected_root_types


class DocumentSession:
    def __init__(self, *, process_cache=PROCESS_DOCUMENT_CACHE, use_process_cache=True):
        self.process_cache = process_cache
        self.use_process_cache = bool(use_process_cache)
        self._documents = {}
        self._documents_by_path = {}
        self._prefetched = {}
        self._warmed_files = set()
        self._prefetch_executor = None
        self._prefetch_workers = 0
        self._issues = []
        self._closed = False

    @property
    def issues(self):
        return tuple(self._issues)

    def prefetch(self, paths, *, expected_kind=None, max_workers=4):
        if self._closed:
            raise RuntimeError("DocumentSession is closed")

        requests = []
        seen = set()
        for path in paths or ():
            if not path:
                continue
            local = LocalPath.from_value(path)
            _, kind, _, _, cache_policy, _ = _source_contract(
                local.value,
                expected_kind,
            )
            path_cache_key = (
                local.key,
                kind.value if kind is not None else "",
            )
            if path_cache_key in seen:
                continue
            seen.add(path_cache_key)
            if path_cache_key in self._documents_by_path:
                continue
            if path_cache_key in self._prefetched:
                continue
            requests.append((local, kind, cache_policy, path_cache_key))

        stats = {
            "requested": len(requests),
            "prefetched": 0,
            "process_cached": 0,
            "failed": 0,
            "bytes": 0,
        }
        if not requests:
            return stats

        def read_request(request):
            local, kind, cache_policy, path_cache_key = request
            try:
                identity = FileIdentity.from_path(local.value)
            except OSError:
                return path_cache_key, None, False
            cache_key = (
                identity.key,
                kind.value if kind is not None else "",
            )
            use_process_cache = (
                self.use_process_cache and cache_policy is CachePolicy.PROCESS
            )
            if use_process_cache and self.process_cache.contains(cache_key):
                return path_cache_key, PrefetchedSource(identity, None), True
            try:
                data = read_bytes(local.value)
            except OSError:
                return path_cache_key, None, False
            return path_cache_key, PrefetchedSource(identity, data), False

        workers = max(1, min(int(max_workers or 1), len(requests)))
        if workers == 1:
            results = map(read_request, requests)
        else:
            if self._prefetch_executor is None:
                self._prefetch_workers = max(4, workers)
                self._prefetch_executor = ThreadPoolExecutor(
                    max_workers=self._prefetch_workers,
                    thread_name_prefix="cp77-doc-prefetch",
                )
            results = tuple(self._prefetch_executor.map(read_request, requests))

        for path_cache_key, source, process_cached in results:
            if source is None:
                stats["failed"] += 1
                continue
            self._prefetched[path_cache_key] = source
            stats["prefetched"] += 1
            if process_cached:
                stats["process_cached"] += 1
            elif source.data is not None:
                stats["bytes"] += len(source.data)
        return stats

    def warm_files(self, paths, *, max_workers=4):
        if self._closed:
            raise RuntimeError("DocumentSession is closed")

        requests = []
        seen = set()
        for path in paths or ():
            if not path:
                continue
            local = LocalPath.from_value(path)
            key = local.key
            if key in seen or key in self._warmed_files:
                continue
            seen.add(key)
            requests.append(local)

        stats = {
            "requested": len(requests),
            "warmed": 0,
            "failed": 0,
            "bytes": 0,
        }
        if not requests:
            return stats

        def warm_request(local):
            try:
                byte_count = warm_file(local.value)
            except OSError:
                return local.key, 0, False
            return local.key, int(byte_count), True

        workers = max(1, min(int(max_workers or 1), len(requests)))
        if workers == 1:
            results = map(warm_request, requests)
        else:
            if self._prefetch_executor is None:
                self._prefetch_workers = max(4, workers)
                self._prefetch_executor = ThreadPoolExecutor(
                    max_workers=self._prefetch_workers,
                    thread_name_prefix="cp77-doc-prefetch",
                )
            results = tuple(self._prefetch_executor.map(warm_request, requests))

        for key, byte_count, succeeded in results:
            if not succeeded:
                stats["failed"] += 1
                continue
            self._warmed_files.add(key)
            stats["warmed"] += 1
            stats["bytes"] += byte_count
        return stats

    def invalidate(self, path):
        """Discard one session snapshot after its source revision changes"""
        key = LocalPath.from_value(path).key
        for cache in (self._documents_by_path, self._prefetched):
            for cache_key in tuple(cache):
                if cache_key[0] == key:
                    del cache[cache_key]
        for cache_key, document in tuple(self._documents.items()):
            if document.identity.path.key == key:
                del self._documents[cache_key]
        self._warmed_files.discard(key)

    def load(self, path, *, expected_kind=None, allow_invalid=True):
        if self._closed:
            raise RuntimeError("DocumentSession is closed")
        local = LocalPath.from_value(path)
        spec, kind, source_format, profile, cache_policy, expected_root_types = (
            _source_contract(local.value, expected_kind)
        )
        path_cache_key = (
            local.key,
            kind.value if kind is not None else "",
        )
        document = self._documents_by_path.get(path_cache_key)
        if document is not None:
            if not allow_invalid and not document.validation.valid:
                return None
            return document
        prefetched = self._prefetched.pop(path_cache_key, None)
        if prefetched is not None:
            identity = prefetched.identity
        else:
            try:
                identity = FileIdentity.from_path(local.value)
            except OSError:
                issue = ResourceIssue(
                    IssueSeverity.ERROR,
                    "file.missing",
                    local.value,
                    f"{local.value}: file does not exist",
                    kind.value if kind is not None else "",
                )
                self._issues.append(issue)
                return None
        if source_format != ResourceFormat.JSON.value:
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "document.format",
                local.value,
                f"{local.value}: resource format is {source_format!r}, expected JSON",
                kind.value if kind is not None else "",
            )
            self._issues.append(issue)
            return None
        cache_key = identity.key, kind.value if kind is not None else ""
        document = self._documents.get(cache_key)
        if document is not None:
            self._documents_by_path[path_cache_key] = document
            if not allow_invalid and not document.validation.valid:
                return None
            return document

        use_process_cache = (
            self.use_process_cache and cache_policy is CachePolicy.PROCESS
        )
        cached = self.process_cache.get(cache_key) if use_process_cache else None
        if cached is not None:
            document = JsonDocument(
                local,
                identity,
                cached.payload,
                cached.resource_kind,
                cached.source_format,
                cached.validation,
            )
        else:
            try:
                source_data = (
                    prefetched.data
                    if prefetched is not None and prefetched.data is not None
                    else _read_json_source(local.value)
                )
                constants = {}
                payload = _decode_json_bytes(
                    source_data,
                    local.value,
                    constants,
                )
            except DocumentLoadError as error:
                self._issues.append(error.issue)
                return None
            validation = validate_payload(
                payload,
                path=local.value,
                kind=kind,
                profile=profile,
                expected_root_types=expected_root_types,
            )
            if constants:
                counts = ", ".join(
                    f"{name} ×{count}" for name, count in sorted(constants.items())
                )
                validation = ValidationResult(
                    validation.issues
                    + (
                        ResourceIssue(
                            IssueSeverity.WARNING,
                            "json.nonfinite",
                            local.value,
                            f"{local.value}: holds non-finite numbers ({counts}); they are read as missing values",
                            kind.value if kind is not None else "",
                        ),
                    )
                )
            if spec is not None and kind is not None and spec.kind is not kind:
                validation = ValidationResult(
                    validation.issues
                    + (
                        ResourceIssue(
                            IssueSeverity.ERROR,
                            "document.resource_kind",
                            local.value,
                            f"{local.value}: suffix identifies {spec.kind.value}, expected {kind.value}",
                            kind.value,
                        ),
                    )
                )
            document = JsonDocument(
                local,
                identity,
                payload,
                kind,
                source_format,
                validation,
            )
            if use_process_cache:
                self.process_cache.store(
                    cache_key,
                    CachedDocument(
                        payload,
                        validation,
                        kind,
                        source_format,
                    ),
                )

        self._documents[cache_key] = document
        self._documents_by_path[path_cache_key] = document
        self._issues.extend(document.validation.issues)
        if not allow_invalid and not document.validation.valid:
            return None
        return document

    def payload(self, path, *, expected_kind=None, allow_invalid=True):
        document = self.load(
            path,
            expected_kind=expected_kind,
            allow_invalid=allow_invalid,
        )
        return document.payload if document is not None else None

    def clear(self):
        self._documents.clear()
        self._documents_by_path.clear()
        self._prefetched.clear()
        self._warmed_files.clear()
        self._issues.clear()

    def close(self):
        if self._prefetch_executor is not None:
            self._prefetch_executor.shutdown(wait=True)
            self._prefetch_executor = None
            self._prefetch_workers = 0
        self.clear()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def load_json_payload(path, *, expected_kind=None, allow_invalid=True):
    with DocumentSession() as documents:
        document = documents.load(
            path,
            expected_kind=expected_kind,
            allow_invalid=allow_invalid,
        )
        if document is not None:
            return copy.deepcopy(document.payload)
        if documents.issues:
            raise DocumentLoadError(documents.issues[-1])
        raise DocumentLoadError(
            ResourceIssue(
                IssueSeverity.ERROR,
                "document.load",
                os.fspath(path),
                f"{os.fspath(path)}: document could not be loaded",
            )
        )


def file_identity(path):
    try:
        return FileIdentity.from_path(path)
    except OSError:
        debug_exception(
            _LOG,
            "Could not read the size and time of %s; its identity carries neither",
            path,
        )
        return FileIdentity(LocalPath.from_value(path), 0, 0)
