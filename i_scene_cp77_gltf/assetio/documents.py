import json
import os
from dataclasses import dataclass

from .cache import PROCESS_DOCUMENT_CACHE, CachedDocument
from .catalog import CachePolicy, ResourceFormat, ResourceKind, resource_export_for_suffix, resource_spec_for_path
from .diagnostics import IssueSeverity, ResourceIssue, ValidationResult
from .paths import LocalPath
from .resolver import full_suffix
from .validation import ValidationProfile, validate_payload


@dataclass(frozen=True, slots=True)
class FileIdentity:
    path: LocalPath
    mtime_ns: int
    size: int

    @classmethod
    def from_path(cls, path):
        local = LocalPath.from_value(path)
        stat_result = os.stat(local.value)
        mtime_ns = getattr(stat_result, "st_mtime_ns", int(stat_result.st_mtime * 1_000_000_000))
        return cls(local, int(mtime_ns), int(stat_result.st_size))

    @property
    def key(self):
        return self.path.key, self.mtime_ns, self.size


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


def _decode_json_bytes(data, path):
    try:
        return json.loads(data.decode("utf-8-sig"))
    except UnicodeDecodeError as error:
        raise DocumentLoadError(ResourceIssue(
            IssueSeverity.ERROR,
            "json.encoding",
            path,
            f"{path}: invalid UTF-8 at byte {error.start}",
        )) from None
    except json.JSONDecodeError as error:
        signature = data[:16]
        if not signature:
            detail = "file is empty"
        elif signature[:4] == b"PK\x03\x04":
            detail = "file is a zip archive, not JSON"
        else:
            detail = f"starts with {signature!r}"
        raise DocumentLoadError(ResourceIssue(
            IssueSeverity.ERROR,
            "json.decode",
            path,
            f"{path}: {error.msg} at line {error.lineno}, column {error.colno} ({detail})",
        )) from None


def _read_json_source(path):
    try:
        with open(path, "rb") as handle:
            return handle.read()
    except OSError as error:
        raise DocumentLoadError(ResourceIssue(
            IssueSeverity.ERROR,
            "file.read",
            path,
            f"{path}: {error}",
        )) from None


def _source_contract(path, expected_kind):
    spec = resource_spec_for_path(path)
    kind = ResourceKind(expected_kind) if expected_kind is not None else (spec.kind if spec is not None else None)
    suffix = full_suffix(path)
    export = resource_export_for_suffix(suffix)
    source_format = export[1].format.value if export is not None else ResourceFormat.JSON.value
    profile = ValidationProfile(spec.validation_profile) if spec is not None else ValidationProfile.NONE
    cache_policy = spec.cache_policy if spec is not None else CachePolicy.SESSION
    expected_root_types = spec.expected_root_types if spec is not None else ()
    return spec, kind, source_format, profile, cache_policy, expected_root_types


class DocumentSession:
    def __init__(self, *, process_cache=PROCESS_DOCUMENT_CACHE, use_process_cache=True):
        self.process_cache = process_cache
        self.use_process_cache = bool(use_process_cache)
        self._documents = {}
        self._issues = []
        self._closed = False

    @property
    def issues(self):
        return tuple(self._issues)

    def load(self, path, *, expected_kind=None, allow_invalid=True):
        if self._closed:
            raise RuntimeError("DocumentSession is closed")
        local = LocalPath.from_value(path)
        if not os.path.isfile(local.value):
            issue = ResourceIssue(
                IssueSeverity.ERROR,
                "file.missing",
                local.value,
                f"{local.value}: file does not exist",
                ResourceKind(expected_kind).value if expected_kind is not None else "",
            )
            self._issues.append(issue)
            return None
        identity = FileIdentity.from_path(local.value)
        spec, kind, source_format, profile, cache_policy, expected_root_types = _source_contract(local.value, expected_kind)
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
            if not allow_invalid and not document.validation.valid:
                return None
            return document

        use_process_cache = self.use_process_cache and cache_policy is CachePolicy.PROCESS
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
                payload = _decode_json_bytes(
                    _read_json_source(local.value),
                    local.value,
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
            if spec is not None and kind is not None and spec.kind is not kind:
                validation = ValidationResult(validation.issues + (ResourceIssue(
                    IssueSeverity.ERROR,
                    "document.resource_kind",
                    local.value,
                    f"{local.value}: suffix identifies {spec.kind.value}, expected {kind.value}",
                    kind.value,
                ),))
            document = JsonDocument(
                local,
                identity,
                payload,
                kind,
                source_format,
                validation,
            )
            if use_process_cache:
                self.process_cache.store(cache_key, CachedDocument(
                    payload,
                    validation,
                    kind,
                    source_format,
                ))

        self._documents[cache_key] = document
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
        self._issues.clear()

    def close(self):
        self.clear()
        self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def file_identity(path):
    try:
        return FileIdentity.from_path(path)
    except OSError:
        return FileIdentity(LocalPath.from_value(path), 0, 0)


def clear_document_cache():
    PROCESS_DOCUMENT_CACHE.clear()


def document_cache_stats():
    return PROCESS_DOCUMENT_CACHE.stats()
