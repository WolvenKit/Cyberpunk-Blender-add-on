from __future__ import annotations

import json
import os
import shutil
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass

from ..core.log import debug_exception, get_logger
from .json_style import JsonStyle, styled_dumps
from .paths import windows_long_path

_LOG = get_logger(__name__)

# Windows file calls stop at 259 characters unless the path is in the extended-length form. The staged and backup
# files sit beside their target, named after it, at most this many characters longer.
_WINDOWS_PATH_LIMIT = 259
_SIBLING_NAME_EXTRA = len("..") + 32 + len(".bak")


@dataclass(frozen=True, slots=True)
class RecoveryFailure:
    path: str
    backup: str | None
    error: str


class AtomicRecoveryError(RuntimeError):
    def __init__(
        self, commit_error: BaseException, failures: tuple[RecoveryFailure, ...]
    ):
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


def _working_path(filepath: str) -> str:
    """filepath made absolute, in the extended-length form when it needs it"""
    path = os.path.abspath(os.fspath(filepath))
    if len(path) + _SIBLING_NAME_EXTRA > _WINDOWS_PATH_LIMIT:
        return windows_long_path(path)
    return path


def _stage_bytes(filepath: str, payload: bytes) -> str:
    path = _working_path(filepath)
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


def _sync_file(path: str) -> None:
    with open(path, "rb+") as stream:
        stream.flush()
        os.fsync(stream.fileno())


def _copy_backup(path: str) -> str:
    backup = _backup_path(path)
    try:
        shutil.copyfile(path, backup)
        _sync_file(backup)
    except Exception:
        _remove_file(backup)
        raise
    return backup


def _is_transient_replace_error(error: OSError) -> bool:
    return isinstance(error, PermissionError) or getattr(error, "winerror", None) in {
        5,
        32,
        33,
    }


def _replace_file(source: str, target: str) -> None:
    delay = 0.01
    for attempt in range(6):
        try:
            os.replace(source, target)
            return
        except OSError as error:
            if attempt == 5 or not _is_transient_replace_error(error):
                raise
            time.sleep(delay)
            delay *= 2.0


def _remove_file(path: str) -> bool:
    """Remove path if it exists, or return False when it could not be removed"""
    try:
        if os.path.exists(path):
            os.unlink(path)
    except OSError as error:
        _LOG.debug("%s was not removed: %s", path, error)
        return False
    return True


def _cleanup_backups(backups: dict[str, str]) -> None:
    for path, backup in backups.items():
        if not _remove_file(backup):
            # The export succeeded; the copy of the file it replaced is left beside it for the user to delete.
            _LOG.warning(
                "The backup of %s could not be removed and remains at %s", path, backup
            )


def _sync_directories(paths) -> None:
    """Make the renames into these files' folders durable"""
    if os.name != "posix":
        return
    for directory in {os.path.dirname(path) or os.curdir for path in paths}:
        try:
            descriptor = os.open(directory, os.O_RDONLY)
        except OSError as error:
            _LOG.debug("Folder %s was not opened for syncing: %s", directory, error)
            continue
        try:
            os.fsync(descriptor)
        except OSError as error:
            _LOG.debug("Folder %s was not synced: %s", directory, error)
        finally:
            os.close(descriptor)


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
            _replace_file(backup, path)
        except OSError as replace_error:
            try:
                shutil.copyfile(backup, path)
                _sync_file(path)
                _remove_file(backup)
            except Exception as copy_error:
                debug_exception(
                    _LOG, "Could not restore %s from its backup %s", path, backup
                )
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
            debug_exception(
                _LOG, "Could not remove %s while recovering an interrupted write", path
            )
            failures.append(RecoveryFailure(path, None, str(error)))

    return tuple(failures)


def _commit_staged(staged: dict[str, str]) -> None:
    staged = {_working_path(path): temporary for path, temporary in staged.items()}
    try:
        # A failed backup changes no target and removes its own copies; the staged files go with the rest.
        backups = _prepare_backups(staged)
        committed = []
        try:
            for path, temporary in staged.items():
                _replace_file(temporary, path)
                committed.append(path)
        except Exception as commit_error:
            failures = _recover_commit(committed, backups)
            if failures:
                raise AtomicRecoveryError(commit_error, failures) from commit_error
            raise
        else:
            _sync_directories(committed)
            _cleanup_backups(backups)
    finally:
        for temporary in staged.values():
            _remove_file(temporary)


def atomic_write_many(payloads: dict[str, bytes]) -> None:
    """Replace related outputs together, restoring every original if the commit fails"""

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
    """Commit already-written temporary files with preservation-first rollback"""

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
        os.makedirs(os.path.dirname(_working_path(target)) or os.curdir, exist_ok=True)
        staged[target] = source
    _commit_staged(staged)


def atomic_write_bytes(filepath: str, payload: bytes) -> None:
    atomic_write_many({filepath: payload})


@contextmanager
def staged_binary_output(filepath: str, payload: bytes):
    """Keep a durable candidate available for validation until its atomic commit"""
    temporary = _stage_bytes(filepath, payload)
    try:
        yield temporary
    finally:
        _remove_file(temporary)


def atomic_write_text(
    filepath: str,
    text: str,
    *,
    encoding: str = "utf-8",
) -> None:
    atomic_write_bytes(filepath, text.encode(encoding))


def atomic_write_json(
    filepath: str, value, *, indent: int = 2, style: JsonStyle | None = None
) -> None:
    """Write value as JSON, in style when given"""
    atomic_write_text(
        filepath,
        styled_dumps(value, style)
        if style is not None
        else json.dumps(value, indent=indent, ensure_ascii=False) + "\n",
    )
