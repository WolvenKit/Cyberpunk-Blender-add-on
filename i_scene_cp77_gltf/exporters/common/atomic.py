from __future__ import annotations

import json
import os
import shutil
import tempfile
import uuid
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RecoveryFailure:
    path: str
    backup: str | None
    error: str


class AtomicRecoveryError(RuntimeError):
    def __init__(self, commit_error: BaseException, failures: tuple[RecoveryFailure, ...]):
        self.commit_error = commit_error
        self.failures = failures
        details = "; ".join(
            f"{failure.path}: {failure.error}"
            + (f"; original preserved at {failure.backup}" if failure.backup else "")
            for failure in failures
        )
        super().__init__(
            f"Atomic export commit failed ({commit_error}); recovery was incomplete: {details}"
        )


def _stage_bytes(filepath: str, payload: bytes) -> str:
    path = os.path.abspath(os.fspath(filepath))
    directory = os.path.dirname(path) or os.curdir
    os.makedirs(directory, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{os.path.basename(path)}.",
        suffix=".tmp",
        dir=directory,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except Exception:
        _remove_file(temporary)
        raise
    return temporary


def _backup_path(path: str) -> str:
    directory = os.path.dirname(path) or os.curdir
    return os.path.join(
        directory,
        f".{os.path.basename(path)}.{uuid.uuid4().hex}.bak",
    )


def _copy_backup(path: str) -> str:
    backup = _backup_path(path)
    try:
        shutil.copy2(path, backup)
        with open(backup, "rb") as stream:
            os.fsync(stream.fileno())
    except Exception:
        _remove_file(backup)
        raise
    return backup


def _remove_file(path: str) -> None:
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError:
        pass


def _cleanup_backups(backups: dict[str, str]) -> None:
    for backup in backups.values():
        _remove_file(backup)


def _prepare_backups(paths) -> dict[str, str]:
    backups = {}
    try:
        for path in paths:
            if os.path.exists(path):
                backups[path] = _copy_backup(path)
    except Exception:
        _cleanup_backups(backups)
        raise
    return backups


def _recover_commit(
    committed: list[str],
    backups: dict[str, str],
) -> tuple[RecoveryFailure, ...]:
    failures = []

    for path, backup in reversed(tuple(backups.items())):
        try:
            os.replace(backup, path)
        except OSError as replace_error:
            try:
                shutil.copy2(backup, path)
                with open(path, "rb") as stream:
                    os.fsync(stream.fileno())
                _remove_file(backup)
            except Exception as copy_error:
                failures.append(
                    RecoveryFailure(
                        path,
                        backup,
                        f"replace restore failed: {replace_error}; "
                        f"copy restore failed: {copy_error}",
                    )
                )

    for path in reversed(committed):
        if path in backups:
            continue
        try:
            if os.path.exists(path):
                os.unlink(path)
        except OSError as error:
            failures.append(RecoveryFailure(path, None, str(error)))

    return tuple(failures)


def _commit_staged(staged: dict[str, str]) -> None:
    backups = _prepare_backups(staged)
    committed = []
    try:
        for path, temporary in staged.items():
            os.replace(temporary, path)
            committed.append(path)
    except Exception as commit_error:
        failures = _recover_commit(committed, backups)
        if failures:
            raise AtomicRecoveryError(commit_error, failures) from commit_error
        raise
    else:
        _cleanup_backups(backups)
    finally:
        for temporary in staged.values():
            _remove_file(temporary)


def atomic_write_many(payloads: dict[str, bytes]) -> None:
    """Replace related outputs without discarding any pre-existing file.

    Every existing target is copied to a durable same-directory backup before the
    first target is changed. A failed commit restores those copies directly over any
    partially written outputs. If restoration itself fails, the original backup is
    deliberately retained and its path is reported in AtomicRecoveryError.
    """

    staged = {}
    identities = set()
    try:
        for filepath, payload in payloads.items():
            path = os.path.abspath(os.fspath(filepath))
            identity = os.path.normcase(path)
            if identity in identities:
                raise ValueError(f"Duplicate atomic output path: {path}")
            identities.add(identity)
            staged[path] = _stage_bytes(path, payload)
    except Exception:
        for temporary in staged.values():
            _remove_file(temporary)
        raise
    _commit_staged(staged)


def atomic_replace_staged(staged_paths: dict[str, str]) -> None:
    """Commit already-written temporary files with preservation-first rollback."""

    staged = {}
    identities = set()
    for path, temporary in staged_paths.items():
        target = os.path.abspath(os.fspath(path))
        source = os.path.abspath(os.fspath(temporary))
        identity = os.path.normcase(target)
        if identity in identities:
            raise ValueError(f"Duplicate atomic output path: {target}")
        identities.add(identity)
        if not os.path.isfile(source):
            raise FileNotFoundError(source)
        os.makedirs(os.path.dirname(target) or os.curdir, exist_ok=True)
        staged[target] = source
    _commit_staged(staged)


def atomic_write_bytes(filepath: str, payload: bytes) -> None:
    atomic_write_many({filepath: payload})


def atomic_write_text(
    filepath: str,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    atomic_write_bytes(filepath, text.encode(encoding))


def atomic_write_json(filepath: str, value, *, indent: int = 2) -> None:
    atomic_write_text(
        filepath,
        json.dumps(value, indent=indent, ensure_ascii=False) + "\n",
    )
